import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock
from agents import boardroom_orchestrator as bo
from agents.boardroom_orchestrator import BoardroomOrchestrator, phase_for_round


def make_agent(name, emoji, turn_order, system_prompt="You are a test agent."):
    a = MagicMock()
    a.name = name
    a.emoji = emoji
    a.turn_order = turn_order
    a.system_prompt = system_prompt
    return a


def test_format_transcript_empty():
    orch = BoardroomOrchestrator(agents=[])
    assert orch._format_transcript([]) == ""


def test_format_transcript_agent_turns():
    orch = BoardroomOrchestrator(agents=[])
    turns = [
        {"role": "agent", "name": "CFO", "content": "We need to cut costs."},
        {"role": "agent", "name": "PM", "content": "Product roadmap requires investment."},
    ]
    result = orch._format_transcript(turns)
    assert "CFO: We need to cut costs." in result
    assert "PM: Product roadmap requires investment." in result


def test_format_transcript_moderator_turn():
    orch = BoardroomOrchestrator(agents=[])
    turns = [{"role": "moderator", "name": "Moderator", "content": "What about timing?"}]
    result = orch._format_transcript(turns)
    assert "[MODERATOR]: What about timing?" in result


def test_build_user_prompt_empty_transcript():
    orch = BoardroomOrchestrator(agents=[])
    agent = make_agent("CFO", "💰", 0)
    prompt = orch._build_user_prompt(agent, "Q3 budget", [])
    assert "Q3 budget" in prompt
    assert "first to speak" in prompt


def test_build_user_prompt_with_transcript():
    orch = BoardroomOrchestrator(agents=[])
    agent = make_agent("DevLead", "🔧", 1)
    transcript = [{"role": "agent", "name": "PM", "content": "Ship fast."}]
    prompt = orch._build_user_prompt(agent, "Launch plan", transcript)
    assert "Launch plan" in prompt
    assert "PM: Ship fast." in prompt


def test_parse_synthesis_with_tasks():
    orch = BoardroomOrchestrator(agents=[])
    content = (
        "The plan is to hire 3 engineers and ship by Q3.\n\n"
        'TASKS_JSON: [{"title": "Hire engineers", "description": "Post JDs", "priority": "high"},'
        '{"title": "Set Q3 deadline", "description": null, "priority": "urgent"}]'
    )
    result = orch._parse_synthesis(content)
    assert "hire 3 engineers" in result["plan"]
    assert len(result["proposed_tasks"]) == 2
    assert result["proposed_tasks"][0]["title"] == "Hire engineers"
    assert result["proposed_tasks"][0]["priority"] == "high"
    assert result["proposed_tasks"][1]["priority"] == "urgent"


def test_parse_synthesis_invalid_json_returns_empty_tasks():
    orch = BoardroomOrchestrator(agents=[])
    content = "Good plan.\n\nTASKS_JSON: not valid json"
    result = orch._parse_synthesis(content)
    assert result["plan"] == "Good plan."
    assert result["proposed_tasks"] == []


def test_parse_synthesis_no_tasks_marker():
    orch = BoardroomOrchestrator(agents=[])
    content = "The plan is straightforward."
    result = orch._parse_synthesis(content)
    assert result["plan"] == "The plan is straightforward."
    assert result["proposed_tasks"] == []


def test_parse_synthesis_rejects_invalid_priority():
    orch = BoardroomOrchestrator(agents=[])
    content = (
        "Plan.\n\n"
        'TASKS_JSON: [{"title": "Do X", "description": null, "priority": "critical"}]'
    )
    result = orch._parse_synthesis(content)
    assert result["proposed_tasks"][0]["priority"] == "medium"


def test_agents_sorted_by_turn_order():
    agents = [
        make_agent("C", "C", turn_order=2),
        make_agent("A", "A", turn_order=0),
        make_agent("B", "B", turn_order=1),
    ]
    orch = BoardroomOrchestrator(agents=agents)
    assert [a.name for a in orch.agents] == ["A", "B", "C"]


# ── Debate-mode prompting ──────────────────────────────────────────────────


def test_phase_for_round_mapping():
    assert phase_for_round(0, 4) == "opening"
    assert phase_for_round(1, 4) == "rebuttal"
    assert phase_for_round(2, 4) == "cross_examination"
    assert phase_for_round(3, 4) == "closing"
    # Single-round debate: each agent speaks once → opening.
    assert phase_for_round(0, 1) == "opening"


def test_structured_prompt_uses_phase_text():
    orch = BoardroomOrchestrator(agents=[])
    agent = make_agent("CFO", "💰", 0)
    prompt = orch._build_user_prompt(
        agent, "Budget", [], mode="structured", round_num=1, total_rounds=3
    )
    assert "PHASE: REBUTTAL" in prompt


def test_tool_hint_appended_when_tools_present():
    orch = BoardroomOrchestrator(agents=[])
    agent = make_agent("CFO", "💰", 0)
    prompt = orch._build_user_prompt(agent, "Budget", [], tools=["web_search"])
    assert "web_search" in prompt
    assert "tools available" in prompt


def test_summarize_tool_result_variants():
    s = BoardroomOrchestrator._summarize_tool_result
    assert "2 results" in s("web_search", {"results": [{"title": "A"}, {"title": "B"}]})
    assert s("calculate", {"expression": "2+2", "result": 4}) == "2+2 = 4"
    assert "error" in s("web_search", {"error": "boom"})


# ── Tool loop ───────────────────────────────────────────────────────────────


def _fake_response(content=None, tool_calls=None):
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _fake_tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=arguments)
    )


@pytest.mark.asyncio
async def test_run_turn_executes_tool_then_completes(monkeypatch):
    orch = BoardroomOrchestrator(agents=[])
    orch.bind_workspace("ws-1")
    agent = make_agent("Researcher", "🔍", 0)

    calls = {"n": 0}

    def fake_chat(*, profile, messages, max_tokens, tools=None, tool_choice=None):
        calls["n"] += 1
        if calls["n"] == 1:
            tc = _fake_tool_call("c1", "web_search", '{"query": "x"}')
            return _fake_response(content="", tool_calls=[tc]), "model"
        return _fake_response(content="Final argument.", tool_calls=None), "model"

    async def fake_execute(name, workspace_id, args):
        assert name == "web_search"
        assert workspace_id == "ws-1"
        return {"results": [{"title": "Z"}]}

    monkeypatch.setattr(bo, "chat_with_fallback", fake_chat)
    monkeypatch.setattr(bo.boardroom_tools, "execute_tool", fake_execute)

    events = [ev async for ev in orch.run_turn(
        agent, "Topic", [], tools=["web_search"]
    )]

    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "turn_complete"]
    assert events[-1]["content"] == "Final argument."
    assert events[-1]["tool_events"][0]["tool"] == "web_search"


@pytest.mark.asyncio
async def test_run_turn_stops_early_when_should_stop(monkeypatch):
    """A 'Stop & summarize' mid-turn must abandon the tool loop at the next
    iteration boundary — not run all MAX_TOOL_ITERS calls."""
    orch = BoardroomOrchestrator(agents=[])
    orch.bind_workspace("ws-1")
    agent = make_agent("Researcher", "🔍", 0)

    calls = {"n": 0}

    def fake_chat(*, profile, messages, max_tokens, tools=None, tool_choice=None):
        # Always asks for another tool → would loop to MAX_TOOL_ITERS without a stop.
        calls["n"] += 1
        tc = _fake_tool_call(f"c{calls['n']}", "web_search", '{"query": "x"}')
        return _fake_response(content="partial reasoning", tool_calls=[tc]), "model"

    async def fake_execute(name, workspace_id, args):
        return {"results": [{"title": "Z"}]}

    monkeypatch.setattr(bo, "chat_with_fallback", fake_chat)
    monkeypatch.setattr(bo.boardroom_tools, "execute_tool", fake_execute)

    stop_flag = {"v": False}

    events = []
    async for ev in orch.run_turn(
        agent, "Topic", [], tools=["web_search"], should_stop=lambda: stop_flag["v"]
    ):
        events.append(ev)
        if ev["type"] == "tool_result":
            stop_flag["v"] = True  # user clicked Stop while the first tool ran

    types = [e["type"] for e in events]
    assert types == ["tool_call", "tool_result", "turn_complete"]
    assert events[-1].get("stopped") is True
    # Only the FIRST LLM call ran; the stop skipped the next iteration's call.
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_run_turn_no_tools_single_shot(monkeypatch):
    orch = BoardroomOrchestrator(agents=[])
    agent = make_agent("PM", "📊", 0)

    def fake_chat(*, profile, messages, max_tokens, tools=None, tool_choice=None):
        assert profile == "agent_chat"
        assert tools is None
        return _fake_response(content="My take.", tool_calls=None), "model"

    monkeypatch.setattr(bo, "chat_with_fallback", fake_chat)

    events = [ev async for ev in orch.run_turn(agent, "Topic", [], tools=[])]
    assert [e["type"] for e in events] == ["turn_complete"]
    assert events[0]["content"] == "My take."
