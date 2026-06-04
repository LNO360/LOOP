"""Tests for Hermes boardroom MCP tools."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Resolver tests (pure, no DB) ─────────────────────────────────────────────

def test_resolve_known_slug_returns_persona():
    from mcp_server.tools.boardroom import _resolve_persona, BOARDROOM_PERSONAS
    result = _resolve_persona("pm")
    assert result["name"] == BOARDROOM_PERSONAS["pm"]["name"]
    assert result["emoji"] == BOARDROOM_PERSONAS["pm"]["emoji"]
    assert len(result["system_prompt"]) > 50


def test_resolve_slug_case_insensitive():
    from mcp_server.tools.boardroom import _resolve_persona
    result = _resolve_persona("PM")
    assert result["name"] == "Product Manager"


def test_resolve_unknown_slug_raises_value_error():
    from mcp_server.tools.boardroom import _resolve_persona
    with pytest.raises(ValueError, match="Unknown persona slug"):
        _resolve_persona("nonexistent-persona")


def test_resolve_error_message_lists_valid_slugs():
    from mcp_server.tools.boardroom import _resolve_persona, BOARDROOM_PERSONAS
    with pytest.raises(ValueError) as exc_info:
        _resolve_persona("bad-slug")
    error_msg = str(exc_info.value)
    for slug in BOARDROOM_PERSONAS:
        assert slug in error_msg


def test_resolve_inline_dict_builds_system_prompt():
    from mcp_server.tools.boardroom import _resolve_persona
    result = _resolve_persona({
        "name": "CFO",
        "emoji": "💰",
        "role": "You focus on budget impact and cash flow.",
    })
    assert result["name"] == "CFO"
    assert result["emoji"] == "💰"
    assert "CFO" in result["system_prompt"]
    assert "budget impact" in result["system_prompt"]


def test_resolve_inline_dict_missing_emoji_defaults():
    from mcp_server.tools.boardroom import _resolve_persona
    result = _resolve_persona({"name": "Lawyer", "role": "Focus on legal risk."})
    assert result["emoji"] == "🤖"


def test_all_persona_slugs_have_required_keys():
    from mcp_server.tools.boardroom import BOARDROOM_PERSONAS
    for slug, data in BOARDROOM_PERSONAS.items():
        assert "name" in data, f"{slug} missing 'name'"
        assert "emoji" in data, f"{slug} missing 'emoji'"
        assert "system_prompt" in data, f"{slug} missing 'system_prompt'"
        assert len(data["system_prompt"]) > 100, f"{slug} system_prompt too short"


# ── lno_list_boardroom_personas ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_boardroom_personas_returns_all_slugs():
    from mcp_server.tools.boardroom import lno_list_boardroom_personas, BOARDROOM_PERSONAS
    result = await lno_list_boardroom_personas()
    returned_slugs = {item["slug"] for item in result}
    assert returned_slugs == set(BOARDROOM_PERSONAS.keys())


@pytest.mark.asyncio
async def test_list_boardroom_personas_has_required_fields():
    from mcp_server.tools.boardroom import lno_list_boardroom_personas
    result = await lno_list_boardroom_personas()
    for item in result:
        assert "slug" in item
        assert "name" in item
        assert "emoji" in item
        assert "focus" in item
        assert len(item["focus"]) > 0


# ── lno_create_boardroom ──────────────────────────────────────────────────────

def _make_mock_db_session(session_id="aaaaaaaa-0000-0000-0000-000000000001"):
    """Returns a mock AsyncSession context manager that yields a mock session."""
    import uuid as _uuid
    mock_session_obj = MagicMock()
    mock_session_obj.id = _uuid.UUID(session_id)
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db._added = []
    def _add(obj):
        if hasattr(obj, "topic"):
            obj.id = mock_session_obj.id
        mock_db._added.append(obj)
    mock_db.add = _add
    return mock_db


@pytest.mark.asyncio
async def test_create_boardroom_returns_session_id():
    from mcp_server.tools.boardroom import lno_create_boardroom
    mock_db = _make_mock_db_session()
    with (
        patch("mcp_server.tools.boardroom.AsyncSessionLocal", return_value=mock_db),
        patch("mcp_server.tools.boardroom.get_workspace_actor_id", new_callable=AsyncMock, return_value=None),
        patch("mcp_server.tools.boardroom.agent_broadcast", new_callable=AsyncMock),
    ):
        result = await lno_create_boardroom(
            workspace_id="aaaaaaaa-0000-0000-0000-000000000000",
            topic="Should we rebuild the auth service?",
            personas=["pm", "ops-monitor"],
            rounds=2,
        )
    assert result["session_id"] == "aaaaaaaa-0000-0000-0000-000000000001"
    assert result["status"] == "setup"
    assert result["rounds"] == 2
    assert len(result["agents"]) == 2
    assert result["agents"][0]["name"] == "Product Manager"
    assert result["agents"][1]["name"] == "Ops Monitor"


@pytest.mark.asyncio
async def test_create_boardroom_rejects_invalid_rounds():
    from mcp_server.tools.boardroom import lno_create_boardroom
    result = await lno_create_boardroom(
        workspace_id="aaaaaaaa-0000-0000-0000-000000000000",
        topic="Test",
        personas=["pm"],
        rounds=0,
    )
    assert "error" in result
    assert "rounds" in result["error"]


@pytest.mark.asyncio
async def test_create_boardroom_rejects_unknown_slug():
    from mcp_server.tools.boardroom import lno_create_boardroom
    result = await lno_create_boardroom(
        workspace_id="aaaaaaaa-0000-0000-0000-000000000000",
        topic="Test",
        personas=["not-a-real-persona"],
        rounds=2,
    )
    assert "error" in result
    assert "Unknown persona slug" in result["error"]


@pytest.mark.asyncio
async def test_create_boardroom_accepts_inline_dict():
    from mcp_server.tools.boardroom import lno_create_boardroom
    mock_db = _make_mock_db_session()
    with (
        patch("mcp_server.tools.boardroom.AsyncSessionLocal", return_value=mock_db),
        patch("mcp_server.tools.boardroom.get_workspace_actor_id", new_callable=AsyncMock, return_value=None),
        patch("mcp_server.tools.boardroom.agent_broadcast", new_callable=AsyncMock),
    ):
        result = await lno_create_boardroom(
            workspace_id="aaaaaaaa-0000-0000-0000-000000000000",
            topic="Budget review",
            personas=[{"name": "CFO", "emoji": "💰", "role": "Focus on financial risk."}],
            rounds=1,
        )
    assert result["status"] == "setup"
    assert result["agents"][0]["name"] == "CFO"
    assert result["agents"][0]["emoji"] == "💰"


@pytest.mark.asyncio
async def test_create_boardroom_rejects_empty_personas():
    from mcp_server.tools.boardroom import lno_create_boardroom
    result = await lno_create_boardroom(
        workspace_id="aaaaaaaa-0000-0000-0000-000000000000",
        topic="Test",
        personas=[],
        rounds=2,
    )
    assert "error" in result


# ── lno_start_boardroom ───────────────────────────────────────────────────────

def _make_start_mocks(
    *,
    session_status="setup",
    rounds=1,
    agent_names=("PM", "Ops Monitor"),
    session_id="bbbbbbbb-0000-0000-0000-000000000001",
    workspace_id="bbbbbbbb-0000-0000-0000-000000000000",
):
    """
    Returns (mock_db_factory, mock_session_obj, mock_agents).
    mock_db_factory() returns the same mock_db each call.
    """
    import uuid as _uuid

    mock_session = MagicMock()
    mock_session.id = _uuid.UUID(session_id)
    mock_session.workspace_id = _uuid.UUID(workspace_id)
    mock_session.topic = "Test topic"
    mock_session.status = session_status
    mock_session.rounds_config = rounds
    mock_session.transcript = []
    mock_session.updated_at = None

    agents = []
    for i, name in enumerate(agent_names):
        a = MagicMock()
        a.id = _uuid.uuid4()
        a.name = name
        a.emoji = "🤖"
        a.turn_order = i
        a.system_prompt = f"You are {name}."
        agents.append(a)

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.commit = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session
    agents_result = MagicMock()
    agents_result.scalars.return_value.all.return_value = agents
    mock_db.execute = AsyncMock(side_effect=[mock_result, agents_result] + [mock_result] * 20)

    class MockDBFactory:
        def __call__(self):
            return mock_db

    return MockDBFactory(), mock_session, agents


@pytest.mark.asyncio
async def test_start_boardroom_happy_path_returns_plan():
    from mcp_server.tools.boardroom import lno_start_boardroom

    db_factory, _, _ = _make_start_mocks(rounds=1, agent_names=("PM",))

    with (
        patch("mcp_server.tools.boardroom.AsyncSessionLocal", db_factory),
        patch("mcp_server.tools.boardroom.agent_broadcast", new_callable=AsyncMock),
        patch(
            "mcp_server.tools.boardroom.BoardroomOrchestrator.get_turn_response",
            new_callable=AsyncMock,
            return_value="I recommend we ship the MVP first.",
        ),
        patch(
            "mcp_server.tools.boardroom.BoardroomOrchestrator.synthesize",
            new_callable=AsyncMock,
            return_value={
                "plan": "Ship MVP in 4 weeks.",
                "proposed_tasks": [
                    {"title": "Scope MVP", "description": "Define scope", "priority": "high"}
                ],
            },
        ),
    ):
        result = await lno_start_boardroom(
            workspace_id="bbbbbbbb-0000-0000-0000-000000000000",
            session_id="bbbbbbbb-0000-0000-0000-000000000001",
        )

    assert result["status"] == "done"
    assert result["plan"] == "Ship MVP in 4 weeks."
    assert len(result["proposed_tasks"]) == 1
    assert result["proposed_tasks"][0]["title"] == "Scope MVP"
    assert result["turns"] == 1


@pytest.mark.asyncio
async def test_start_boardroom_multiple_agents_multiple_rounds():
    from mcp_server.tools.boardroom import lno_start_boardroom

    db_factory, _, _ = _make_start_mocks(rounds=2, agent_names=("PM", "CTO"))

    turn_responses = []
    with (
        patch("mcp_server.tools.boardroom.AsyncSessionLocal", db_factory),
        patch("mcp_server.tools.boardroom.agent_broadcast", new_callable=AsyncMock),
        patch(
            "mcp_server.tools.boardroom.BoardroomOrchestrator.get_turn_response",
            new_callable=AsyncMock,
            side_effect=lambda agent, topic, transcript: (
                turn_responses.append(agent.name) or f"{agent.name} spoke."
            ),
        ),
        patch(
            "mcp_server.tools.boardroom.BoardroomOrchestrator.synthesize",
            new_callable=AsyncMock,
            return_value={"plan": "Done.", "proposed_tasks": []},
        ),
    ):
        result = await lno_start_boardroom(
            workspace_id="bbbbbbbb-0000-0000-0000-000000000000",
            session_id="bbbbbbbb-0000-0000-0000-000000000001",
        )

    # 2 agents × 2 rounds = 4 turns
    assert result["turns"] == 4
    assert result["status"] == "done"


@pytest.mark.asyncio
async def test_start_boardroom_session_not_found():
    from mcp_server.tools.boardroom import lno_start_boardroom

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    not_found = MagicMock()
    not_found.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=not_found)

    with patch("mcp_server.tools.boardroom.AsyncSessionLocal", return_value=mock_db):
        result = await lno_start_boardroom(
            workspace_id="cccccccc-0000-0000-0000-000000000000",
            session_id="cccccccc-0000-0000-0000-000000000001",
        )

    assert "error" in result
    assert "not found" in result["error"]


@pytest.mark.asyncio
async def test_start_boardroom_already_running_returns_error():
    from mcp_server.tools.boardroom import lno_start_boardroom

    db_factory, _, _ = _make_start_mocks(session_status="running")

    with patch("mcp_server.tools.boardroom.AsyncSessionLocal", db_factory):
        result = await lno_start_boardroom(
            workspace_id="bbbbbbbb-0000-0000-0000-000000000000",
            session_id="bbbbbbbb-0000-0000-0000-000000000001",
        )

    assert "error" in result
    assert "running" in result["error"]


@pytest.mark.asyncio
async def test_start_boardroom_llm_failure_continues_session():
    """A turn failure must not abort the session — synthesis still runs."""
    from mcp_server.tools.boardroom import lno_start_boardroom

    db_factory, _, _ = _make_start_mocks(rounds=1, agent_names=("PM",))

    with (
        patch("mcp_server.tools.boardroom.AsyncSessionLocal", db_factory),
        patch("mcp_server.tools.boardroom.agent_broadcast", new_callable=AsyncMock),
        patch(
            "mcp_server.tools.boardroom.BoardroomOrchestrator.get_turn_response",
            new_callable=AsyncMock,
            side_effect=Exception("LLM timeout"),
        ),
        patch(
            "mcp_server.tools.boardroom.BoardroomOrchestrator.synthesize",
            new_callable=AsyncMock,
            return_value={"plan": "Partial plan.", "proposed_tasks": []},
        ),
    ):
        result = await lno_start_boardroom(
            workspace_id="bbbbbbbb-0000-0000-0000-000000000000",
            session_id="bbbbbbbb-0000-0000-0000-000000000001",
        )

    assert result["status"] == "done"
    assert result["plan"] == "Partial plan."
