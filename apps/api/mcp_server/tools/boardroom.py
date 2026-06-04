"""
MCP tools for Hermes-initiated boardroom sessions.

Read tools  (immediate): lno_list_boardroom_personas
Write tools (immediate): lno_create_boardroom, lno_start_boardroom
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Union

from sqlalchemy import select

from agents.boardroom_orchestrator import BoardroomOrchestrator
from db.session import AsyncSessionLocal
from mcp_server.helpers import get_workspace_actor_id
from mcp_server.server import agent_broadcast, mcp
from models.boardroom import BoardroomAgent, BoardroomSession

# ── Persona registry ──────────────────────────────────────────────────────────

BOARDROOM_PERSONAS: dict[str, dict] = {
    "pm": {
        "name": "Product Manager",
        "emoji": "📊",
        "system_prompt": (
            "You are a Product Manager with operational responsibility for delivery timelines "
            "and user outcomes. You have a bias toward shipping: you challenge over-engineering "
            "and push for the smallest change that delivers user value. When someone proposes a "
            "complex solution, ask: what is the MVP? Can we validate this assumption before "
            "building the full system? Take a clear stance on what should be built, deferred, or "
            "dropped — do not just list tradeoffs. Reference project execution data when available."
        ),
    },
    "github-watcher": {
        "name": "GitHub Watcher",
        "emoji": "👁️",
        "system_prompt": (
            "You are an engineering monitoring agent who tracks PRs, CI status, and repository "
            "health daily. You speak in specifics: stale PRs, blocked reviews, failing pipelines. "
            "Challenge plans that ignore the current engineering state — if there are blocked PRs, "
            "any plan that does not address them is incomplete. You will not accept abstract "
            "timelines when engineering signals contradict them. Take a position on what the "
            "engineering data says about feasibility of what is being proposed."
        ),
    },
    "engineering-ops-lead": {
        "name": "Engineering Ops Lead",
        "emoji": "⚙️",
        "system_prompt": (
            "You are the Engineering Ops Lead responsible for cross-team coordination and delivery "
            "reliability. You synthesize engineering signals (PRs, CI) and project execution "
            "(task velocity, milestone drift) into operational intelligence. Challenge both "
            "speed-focused plans that ignore coordination risk and cautious plans that ignore "
            "delivery urgency. State the biggest systemic risk early and defend it. Do not "
            "summarize what others said — add what they are missing."
        ),
    },
    "ops-monitor": {
        "name": "Ops Monitor",
        "emoji": "🔍",
        "system_prompt": (
            "You are a skeptical operations lead who has watched projects fail due to overconfidence. "
            "Optimistic timelines are almost always wrong, vendor promises break at scale, and "
            "'we will fix it in production' is how companies burn money. When someone proposes "
            "something, ask: what breaks at 10x load? What is the true maintenance cost? Who owns "
            "this at 2am? Disagree loudly with anyone who underestimates operational complexity. "
            "Do not hedge. Say what you actually believe and why others are wrong where they are."
        ),
    },
    "cto": {
        "name": "CTO",
        "emoji": "🤖",
        "system_prompt": (
            "You are a CTO focused on technical architecture and long-term system health. Challenge "
            "short-term fixes that create technical debt and push back on business pressure that "
            "ignores technical reality. Evaluate any plan: does this scale? Does this add complexity "
            "we cannot maintain? Are we solving the symptom or the root cause? Hold strong positions "
            "on technical approach even under product pressure — state your recommendation and "
            "defend it."
        ),
    },
    "devil-advocate": {
        "name": "Devil's Advocate",
        "emoji": "😈",
        "system_prompt": (
            "You are a Devil's Advocate. Challenge the premise of whatever the group is converging "
            "on. Ask: are we solving the right problem? What is the strongest argument against the "
            "emerging consensus? What are we not considering? Do not propose alternative solutions — "
            "expose weaknesses in the current thinking so better solutions can emerge. Be specific "
            "about what is wrong, not vague about risk."
        ),
    },
}


def _resolve_persona(p: Union[str, dict]) -> dict:
    """
    Resolve a persona entry to {name, emoji, system_prompt}.
    Accepts a slug string or an inline dict {name, emoji, role}.
    Raises ValueError with the list of valid slugs for unknown slugs.
    """
    if isinstance(p, str):
        slug = p.strip().lower()
        if slug not in BOARDROOM_PERSONAS:
            valid = ", ".join(BOARDROOM_PERSONAS.keys())
            raise ValueError(f"Unknown persona slug '{slug}'. Valid slugs: {valid}")
        return BOARDROOM_PERSONAS[slug]
    # Inline dict path
    name = str(p.get("name", "Agent")).strip()
    emoji = str(p.get("emoji", "🤖"))
    role = str(p.get("role", "")).strip()
    system_prompt = (
        f"You are a {name}. {role}\n\n"
        "You have a distinct point of view shaped by this role. When others speak, find what "
        "you genuinely disagree with and say so by name. Do not perform balance or list pros "
        "and cons — take a position and defend it. If you change your mind, say explicitly "
        "what moved you."
    )
    return {"name": name, "emoji": emoji, "system_prompt": system_prompt}


@mcp.tool()
async def lno_list_boardroom_personas() -> list[dict]:
    """
    Return all built-in boardroom persona slugs and their descriptions.
    Call this before lno_create_boardroom to discover available agent types.
    Personas can be combined freely; 2-4 agents per session is recommended.
    Returns: [{"slug": str, "name": str, "emoji": str, "focus": str}]
    """
    return [
        {
            "slug": slug,
            "name": data["name"],
            "emoji": data["emoji"],
            "focus": data["system_prompt"].split(".")[0],
        }
        for slug, data in BOARDROOM_PERSONAS.items()
    ]


@mcp.tool()
async def lno_create_boardroom(
    workspace_id: str,
    topic: str,
    personas: list,
    rounds: int = 2,
) -> dict:
    """
    Create a boardroom session with the given personas and topic. No LLM calls — returns immediately.

    personas: list of slug strings (e.g. ["pm", "github-watcher"]) or inline dicts
              {"name": str, "emoji": str, "role": str}. Mixed lists are allowed.
    rounds:   number of deliberation rounds per agent (1-5, default 2).

    Call lno_list_boardroom_personas() first to see available slug values.
    Follow with lno_start_boardroom(workspace_id, session_id) to run the discussion.

    Returns: {"session_id": str, "topic": str, "status": "setup", "rounds": int, "agents": list}
    On error: {"error": str}
    """
    if not (1 <= rounds <= 5):
        return {"error": "rounds must be between 1 and 5"}
    if not personas:
        return {"error": "at least one persona is required"}

    try:
        resolved = [_resolve_persona(p) for p in personas]
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        ws_uuid = uuid.UUID(workspace_id)
    except ValueError:
        return {"error": f"Invalid workspace_id: '{workspace_id}'"}
    actor_id = await get_workspace_actor_id(ws_uuid)

    async with AsyncSessionLocal() as db:
        session = BoardroomSession(
            workspace_id=ws_uuid,
            topic=topic,
            status="setup",
            rounds_config=rounds,
            transcript=[],
            created_by=actor_id,
        )
        db.add(session)
        await db.flush()

        agents_out = []
        for i, persona in enumerate(resolved):
            agent = BoardroomAgent(
                session_id=session.id,
                name=persona["name"],
                emoji=persona["emoji"],
                persona_type="builtin" if isinstance(personas[i], str) else "adhoc",
                system_prompt=persona["system_prompt"],
                turn_order=i,
            )
            db.add(agent)
            agents_out.append({
                "name": persona["name"],
                "emoji": persona["emoji"],
                "turn_order": i,
            })

        await db.commit()
        session_id = str(session.id)

    await agent_broadcast(
        workspace_id,
        "lno_create_boardroom",
        "done",
        f"Created boardroom: '{topic[:60]}' with {len(resolved)} agent(s)",
    )
    return {
        "session_id": session_id,
        "topic": topic,
        "status": "setup",
        "rounds": rounds,
        "agents": agents_out,
    }


@mcp.tool()
async def lno_start_boardroom(workspace_id: str, session_id: str) -> dict:
    """
    Run a boardroom session to completion. Blocks until all rounds and synthesis are done.

    Agents deliberate in round-robin order for the configured number of rounds,
    then a synthesis agent produces a structured action plan and proposed tasks.
    The session transcript and output are persisted to the database and visible in the UI.

    Returns: {"session_id": str, "status": "done", "plan": str, "proposed_tasks": list, "turns": int}
    On error: {"error": str} for invalid input, or {"session_id": str, "error": str} for missing session.
    """
    try:
        _session_uuid = uuid.UUID(session_id)
        _workspace_uuid = uuid.UUID(workspace_id)
    except ValueError:
        return {"error": "Invalid session_id or workspace_id", "session_id": session_id}

    # ── Load session ──────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        s_result = await db.execute(
            select(BoardroomSession).where(
                BoardroomSession.id == _session_uuid,
                BoardroomSession.workspace_id == _workspace_uuid,
            )
        )
        session = s_result.scalar_one_or_none()
        if not session:
            return {"error": f"Session {session_id} not found", "session_id": session_id}
        if session.status not in ("setup", "paused"):
            return {
                "error": f"Session is already '{session.status}', cannot start",
                "session_id": session_id,
                "status": session.status,
            }

        a_result = await db.execute(
            select(BoardroomAgent)
            .where(BoardroomAgent.session_id == session.id)
            .order_by(BoardroomAgent.turn_order)
        )
        agents = list(a_result.scalars().all())
        topic = session.topic
        rounds_config = session.rounds_config
        transcript: list[dict] = list(session.transcript or [])

        session.status = "running"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()

    # ── Run discussion ────────────────────────────────────────────────────────
    orchestrator = BoardroomOrchestrator(agents)

    async def _persist_transcript(t: list[dict]) -> None:
        async with AsyncSessionLocal() as db:
            r = await db.execute(
                select(BoardroomSession).where(BoardroomSession.id == uuid.UUID(session_id))
            )
            s = r.scalar_one_or_none()
            if s:
                s.transcript = t
                s.updated_at = datetime.now(timezone.utc)
                await db.commit()

    for round_num in range(rounds_config):
        for agent in orchestrator.agents:
            label = f"{agent.emoji} {agent.name} — round {round_num + 1}/{rounds_config}"
            await agent_broadcast(workspace_id, "lno_start_boardroom", "running", label)
            try:
                full_text = await orchestrator.get_turn_response(agent, topic, transcript)
            except Exception as exc:
                full_text = f"[{agent.name} encountered an error: {exc}]"
            transcript.append({
                "role": "agent",
                "agent_id": str(agent.id),
                "name": agent.name,
                "emoji": agent.emoji,
                "content": full_text,
                "round": round_num + 1,
            })
            await _persist_transcript(transcript)

    # ── Synthesize ────────────────────────────────────────────────────────────
    await agent_broadcast(workspace_id, "lno_start_boardroom", "running", "Synthesizing plan…")
    output = await orchestrator.synthesize(topic, transcript)

    # ── Persist output ────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            select(BoardroomSession).where(BoardroomSession.id == uuid.UUID(session_id))
        )
        s = r.scalar_one_or_none()
        if s:
            s.output = output
            s.status = "done"
            s.updated_at = datetime.now(timezone.utc)
            await db.commit()

    task_count = len(output.get("proposed_tasks", []))
    await agent_broadcast(
        workspace_id,
        "lno_start_boardroom",
        "done",
        f"Boardroom complete — {task_count} task{'s' if task_count != 1 else ''} proposed",
    )
    agent_turns = [t for t in transcript if t.get("role") == "agent"]
    return {
        "session_id": session_id,
        "status": "done",
        "plan": output.get("plan", ""),
        "proposed_tasks": output.get("proposed_tasks", []),
        "turns": len(agent_turns),
    }
