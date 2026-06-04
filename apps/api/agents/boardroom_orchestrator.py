"""
BoardroomOrchestrator — drives a single boardroom session.

Each agent is called independently via asyncio.to_thread so the sync OpenRouter
client does not block the event loop. Agents read the full transcript but reason
from their own system_prompt, giving authentic divergent perspectives.

Agents may be given tools (core/boardroom_tools.py). When an agent has tools, its
turn runs a bounded function-calling loop: the model may call tools, we execute them
directly, feed results back, and iterate until it produces prose. The session's
debate_mode shapes the per-turn instructions (round-robin / structured phases /
dynamic challenges).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, AsyncIterator, Callable

from core import boardroom_tools
from core.model_router import chat_with_fallback

if TYPE_CHECKING:
    from models.boardroom import BoardroomAgent

logger = logging.getLogger(__name__)

# Bound the tool-calling loop so a single turn can't run forever.
MAX_TOOL_ITERS = 4

VALID_MODES = {"round_robin", "structured", "dynamic"}


def phase_for_round(round_num: int, total_rounds: int) -> str:
    """Map a 0-indexed round to a structured-debate phase."""
    if round_num <= 0:
        return "opening"
    if round_num >= total_rounds - 1:
        return "closing"
    if round_num == 1:
        return "rebuttal"
    return "cross_examination"


_PHASE_INSTRUCTIONS = {
    "opening": (
        "PHASE: OPENING STATEMENT. State your position on the topic clearly and "
        "directly. What do you recommend, and what is the single biggest risk you see? "
        "Take a stance — no hedging, no listing 'considerations'."
    ),
    "rebuttal": (
        "PHASE: REBUTTAL. Pick the position you most disagree with and dismantle it by "
        "name. Cite specific weaknesses. Then strengthen your own stance with one new "
        "point or piece of evidence not yet raised."
    ),
    "cross_examination": (
        "PHASE: CROSS-EXAMINATION. Press the hardest question at whoever is most wrong. "
        "Demand specifics. Concede only what is genuinely conceded — and say what changed "
        "your mind if anything did. Introduce a fact or constraint nobody has addressed."
    ),
    "closing": (
        "PHASE: CLOSING ARGUMENT. No new threads. Land your final, actionable "
        "recommendation. Be explicit about what you would do, in what order, and the one "
        "risk you accept by doing so."
    ),
}


class BoardroomOrchestrator:
    def __init__(self, agents: list["BoardroomAgent"]):
        self.agents = sorted(agents, key=lambda a: a.turn_order)

    # ── Pure helpers (unit-testable) ───────────────────────────────────────

    def _format_transcript(self, turns: list[dict]) -> str:
        if not turns:
            return ""
        lines = []
        for turn in turns:
            role = turn.get("role", "agent")
            name = turn.get("name", "Agent")
            content = turn.get("content", "")
            if role == "moderator":
                lines.append(f"[MODERATOR]: {content}")
            else:
                lines.append(f"{name}: {content}")
        return "\n\n".join(lines)

    def _tool_hint(self, tools: list[str]) -> str:
        if not tools:
            return ""
        names = ", ".join(tools)
        return (
            f"\n\nYou have tools available: {names}. Use them to gather real evidence "
            "before arguing — don't speculate when you can check. Cite what you found "
            "(numbers, sources) in your argument. Keep tool use focused (a few calls max)."
        )

    def _build_user_prompt(
        self,
        agent: "BoardroomAgent",
        topic: str,
        transcript: list[dict],
        *,
        mode: str = "round_robin",
        round_num: int = 0,
        total_rounds: int = 1,
        tools: list[str] | None = None,
    ) -> str:
        tools = tools or []
        transcript_text = self._format_transcript(transcript)
        tool_hint = self._tool_hint(tools)

        # Structured mode is phase-driven and self-contained.
        if mode == "structured":
            phase = phase_for_round(round_num, total_rounds)
            head = f"Topic: {topic}\n\n"
            if transcript_text:
                head += f"Discussion so far:\n{transcript_text}\n\n"
            return (
                f"{head}You are {agent.name}.\n{_PHASE_INSTRUCTIONS[phase]}\n"
                "If the [MODERATOR] raised a point, address it first."
                f"{tool_hint}"
            )

        # First voice with no transcript (round_robin / dynamic opening).
        if not transcript_text:
            return (
                f"Topic: {topic}\n\n"
                f"You are {agent.name}. You are first to speak. State your position clearly and directly:\n"
                "- What is your recommendation or conclusion?\n"
                "- What is the single biggest risk or concern you see?\n"
                "- What specific evidence or reasoning drives your view?\n\n"
                "Be concrete. No hedging. No listing 'considerations' — take a stance."
                f"{tool_hint}"
            )

        prior_agent_turns = [
            t for t in transcript if t.get("name") == agent.name and t.get("role") == "agent"
        ]
        if prior_agent_turns:
            position_reminder = (
                f"Your earlier position: \"{prior_agent_turns[-1]['content'][:300]}...\"\n\n"
                "Either defend it against what others said, or explicitly say what changed your mind and why.\n"
            )
        else:
            position_reminder = ""

        return (
            f"Topic: {topic}\n\n"
            f"Discussion so far:\n{transcript_text}\n\n"
            f"You are {agent.name}.\n"
            f"{position_reminder}"
            "Rules for this turn:\n"
            "1. Pick at least one thing someone said above that you DISAGREE with. Challenge it directly by name.\n"
            "2. Do not simply validate or summarize what others said.\n"
            "3. Introduce at least one specific point, fact, or constraint that has NOT been raised yet.\n"
            "4. End with a clear, actionable recommendation — not open questions.\n\n"
            "If the [MODERATOR] raised a point, address it first."
            f"{tool_hint}"
        )

    def _parse_synthesis(self, content: str) -> dict:
        plan = content.strip()
        tasks: list[dict] = []
        if "TASKS_JSON:" in content:
            parts = content.split("TASKS_JSON:", 1)
            plan = parts[0].strip()
            tasks_raw = parts[1].strip()
            try:
                start = tasks_raw.find("[")
                end = tasks_raw.rfind("]") + 1
                if start != -1 and end > start:
                    parsed = json.loads(tasks_raw[start:end])
                    valid_priorities = {"low", "medium", "high", "urgent"}
                    tasks = [
                        {
                            "title": str(t.get("title", ""))[:80],
                            "description": t.get("description"),
                            "priority": t.get("priority", "medium")
                            if t.get("priority") in valid_priorities
                            else "medium",
                        }
                        for t in parsed[:10]
                        if isinstance(t, dict) and t.get("title")
                    ]
            except Exception:
                pass
        return {"plan": plan, "proposed_tasks": tasks}

    @staticmethod
    def _summarize_tool_result(name: str, result: dict) -> str:
        if "error" in result:
            return f"error: {result['error']}"
        if name == "web_search":
            res = result.get("results", [])
            if res and isinstance(res[0], dict) and "error" in res[0]:
                return f"error: {res[0]['error']}"
            top = res[0].get("title") if res else None
            return f"{len(res)} results" + (f" — top: {top}" if top else "")
        if name == "web_fetch_page":
            return f"{result.get('total_chars', 0)} chars from {result.get('url', '')}"
        if name == "calculate":
            return f"{result.get('expression', '')} = {result.get('result', '')}"
        if name == "propose_task":
            return "task proposed for approval"
        # Generic: compact json
        s = json.dumps(result)
        return s if len(s) <= 160 else s[:157] + "…"

    # ── Async LLM calls ────────────────────────────────────────────────────

    async def run_turn(
        self,
        agent: "BoardroomAgent",
        topic: str,
        transcript: list[dict],
        *,
        tools: list[str] | None = None,
        mode: str = "round_robin",
        round_num: int = 0,
        total_rounds: int = 1,
        should_stop: Callable[[], bool] | None = None,
    ) -> AsyncIterator[dict]:
        """
        Run one agent turn, yielding event dicts:
          {"type": "tool_call",   "tool": str, "args": dict}
          {"type": "tool_result", "tool": str, "summary": str}
          {"type": "turn_complete", "content": str, "tool_events": list}
        The final event is always turn_complete.

        If ``should_stop`` is supplied and returns True at a tool-loop boundary,
        the turn is abandoned immediately (no further LLM call) and the final
        event carries ``stopped=True`` with whatever partial reasoning exists.
        This is what makes "Stop & summarize" responsive mid-turn.
        """
        tools = [t for t in (tools or []) if t in boardroom_tools.tool_names()]
        user_prompt = self._build_user_prompt(
            agent, topic, transcript,
            mode=mode, round_num=round_num, total_rounds=total_rounds, tools=tools,
        )
        messages: list[dict] = [
            {"role": "system", "content": agent.system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        schemas = boardroom_tools.tool_schemas(tools) if tools else None
        tool_events: list[dict] = []
        last_partial = ""

        try:
            for _ in range(MAX_TOOL_ITERS):
                # "Stop & summarize" clicked mid-turn → bail at this boundary
                # rather than firing another (possibly tool-laden) LLM call.
                if should_stop and should_stop():
                    yield {
                        "type": "turn_complete",
                        "content": last_partial,
                        "tool_events": tool_events,
                        "stopped": True,
                    }
                    return

                profile = "agent_tools" if schemas else "agent_chat"

                def _sync_call():
                    return chat_with_fallback(
                        profile=profile,
                        messages=messages,
                        max_tokens=800,
                        tools=schemas,
                        tool_choice="auto" if schemas else None,
                    )

                response, _ = await asyncio.to_thread(_sync_call)
                msg = response.choices[0].message
                tool_calls = getattr(msg, "tool_calls", None)

                if not tool_calls:
                    text = msg.content or ""
                    yield {"type": "turn_complete", "content": text, "tool_events": tool_events}
                    return

                # Keep the latest interim reasoning in case a stop cuts us off
                # before the model produces its final prose.
                if msg.content:
                    last_partial = msg.content

                # Record the assistant's tool-call message so the model keeps context.
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {}
                    yield {"type": "tool_call", "tool": name, "args": args}

                    result = await boardroom_tools.execute_tool(name, self._workspace_id, args)
                    summary = self._summarize_tool_result(name, result)
                    tool_events.append({"tool": name, "args": args, "summary": summary})
                    yield {"type": "tool_result", "tool": name, "summary": summary}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result)[:4000],
                    })

            # Hit the iteration cap: ask once more for a final answer, no tools.
            messages.append({
                "role": "user",
                "content": "Stop using tools now. Give your argument and recommendation based on what you found.",
            })

            def _final_call():
                return chat_with_fallback(
                    profile="agent_chat", messages=messages, max_tokens=800,
                )

            response, _ = await asyncio.to_thread(_final_call)
            text = response.choices[0].message.content or ""
            yield {"type": "turn_complete", "content": text, "tool_events": tool_events}

        except Exception as e:
            logger.error(f"[boardroom] agent={agent.name} turn failed: {e}")
            yield {
                "type": "turn_complete",
                "content": f"[{agent.name} encountered an error and skipped their turn]",
                "tool_events": tool_events,
            }

    # Workspace context for tool execution; set by the caller before run_turn.
    _workspace_id: str = ""

    def bind_workspace(self, workspace_id: str) -> None:
        self._workspace_id = workspace_id

    async def get_turn_response(
        self, agent: "BoardroomAgent", topic: str, transcript: list[dict]
    ) -> str:
        """Backwards-compatible single-string turn (no tools, round-robin)."""
        text = ""
        async for ev in self.run_turn(agent, topic, transcript):
            if ev["type"] == "turn_complete":
                text = ev["content"]
        return text

    async def moderator_challenge(self, topic: str, transcript: list[dict]) -> str:
        """
        Dynamic mode: name the sharpest disagreement and direct one agent to rebut
        another. Returns a short moderator line (empty string on failure).
        """
        transcript_text = self._format_transcript(transcript)
        if not transcript_text:
            return ""
        agent_names = ", ".join(a.name for a in self.agents)
        system = (
            "You are a sharp debate moderator. Read the discussion and find the single "
            "most important unresolved disagreement. Output ONE sentence that names a "
            "specific agent and directs them to respond to another agent's specific "
            "claim. Be pointed. No preamble."
        )
        user = (
            f"Topic: {topic}\nAgents: {agent_names}\n\nDiscussion:\n{transcript_text}\n\n"
            "Your one-sentence challenge:"
        )

        def _sync_call() -> str:
            response, _ = chat_with_fallback(
                profile="agent_chat",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=120,
            )
            return response.choices[0].message.content or ""

        try:
            return (await asyncio.to_thread(_sync_call)).strip()
        except Exception as e:
            logger.warning(f"[boardroom] moderator_challenge failed: {e}")
            return ""

    def _synthesis_messages(self, topic: str, transcript: list[dict]) -> list[dict]:
        transcript_text = self._format_transcript(transcript)
        system = (
            "You are a synthesis agent. Read the boardroom discussion and produce a decision brief.\n\n"
            "Structure your response as:\n"
            "**Decision:** One sentence stating what was decided and why.\n\n"
            "**Key disagreements resolved:** What did agents actually disagree on? How was it resolved or left open?\n\n"
            "**Action plan:** 2-3 concrete paragraphs. What must happen, in what order, and who owns what type of work.\n\n"
            "**Risks acknowledged:** The 1-2 risks the group could not fully resolve.\n\n"
            "Then output tasks:\n"
            'TASKS_JSON: [{"title": "...", "description": "...", "priority": "low|medium|high|urgent"}]\n\n'
            "Do not summarize what each person said. Synthesize what was decided."
        )
        user = f"Topic: {topic}\n\nDiscussion transcript:\n{transcript_text}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    async def synthesize_stream(
        self, topic: str, transcript: list[dict]
    ) -> AsyncIterator[str]:
        """
        Stream the synthesis as raw text deltas so the client can render the
        decision brief as it is written. Yields nothing on failure — the caller
        should fall back to the blocking ``synthesize`` when the stream is empty.
        """
        messages = self._synthesis_messages(topic, transcript)

        def _open():
            from core.model_router import create_stream_with_fallback
            return create_stream_with_fallback(
                profile="project_manager", messages=messages, max_tokens=1500,
            )

        try:
            stream, _ = await asyncio.to_thread(_open)
        except Exception as e:
            logger.error(f"[boardroom] synthesis stream failed to open: {e}")
            return

        # Each next() is a blocking network read → off-load to a thread so the
        # event loop (and the rest of the SSE connection) stays responsive.
        sentinel = object()
        while True:
            try:
                chunk = await asyncio.to_thread(next, stream, sentinel)
            except Exception as e:
                logger.warning(f"[boardroom] synthesis stream interrupted: {e}")
                return
            if chunk is sentinel:
                return
            try:
                delta = chunk.choices[0].delta.content or ""
            except (AttributeError, IndexError):
                delta = ""
            if delta:
                yield delta

    async def synthesize(self, topic: str, transcript: list[dict]) -> dict:
        messages = self._synthesis_messages(topic, transcript)

        def _sync_call() -> str:
            response, _ = chat_with_fallback(
                profile="project_manager",
                messages=messages,
                max_tokens=1500,
            )
            return response.choices[0].message.content or ""

        try:
            content = await asyncio.to_thread(_sync_call)
            return self._parse_synthesis(content)
        except Exception as e:
            logger.error(f"[boardroom] synthesis failed: {e}")
            # fallback: expose the raw transcript as the plan
            return {"plan": self._format_transcript(transcript), "proposed_tasks": []}
