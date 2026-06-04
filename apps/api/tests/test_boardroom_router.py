"""
Integration tests for boardroom CRUD endpoints.
SSE streaming endpoint is not tested here (requires a live LLM call).
"""
import pytest
from httpx import AsyncClient

TEST_EMAIL = "boardroom_test@example.com"
TEST_PASSWORD = "testpass123"


async def _signup_and_get_ids(client: AsyncClient) -> tuple[str, str]:
    """Sign up (or reuse) a user; return (token, workspace_id)."""
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Boardroom Tester",
            "workspace_name": "Boardroom Test WS",
        },
    )
    # 400 = already exists; log in instead
    if r.status_code == 400:
        r = await client.post(
            "/api/v1/auth/login",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        # Fetch workspaces to get an id
        r2 = await client.get(
            "/api/v1/workspaces",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200, r2.text
        workspace_id = r2.json()[0]["id"]
        return token, workspace_id

    assert r.status_code in (200, 201), r.text
    data = r.json()
    return data["token"], data["workspace_id"]


def _adhoc_agent(name: str, emoji: str, order: int) -> dict:
    return {
        "name": name,
        "emoji": emoji,
        "persona_type": "adhoc",
        "system_prompt": f"You are {name}.",
        "turn_order": order,
    }


@pytest.mark.asyncio
async def test_create_and_list_session(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions",
        json={
            "topic": "Should we expand to new markets?",
            "rounds_config": 1,
            "agents": [
                _adhoc_agent("CFO", "💰", 0),
                _adhoc_agent("Growth Lead", "📈", 1),
            ],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session = r.json()
    assert session["topic"] == "Should we expand to new markets?"
    assert session["status"] == "setup"
    assert session["rounds_config"] == 1
    assert len(session["agents"]) == 2
    session_id = session["id"]

    r = await client.get(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions", headers=headers
    )
    assert r.status_code == 200, r.text
    sessions = r.json()["sessions"]
    assert any(s["id"] == session_id for s in sessions)


@pytest.mark.asyncio
async def test_get_session(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions",
        json={
            "topic": "Tech stack decision",
            "rounds_config": 2,
            "agents": [_adhoc_agent("CTO", "🔧", 0)],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    r = await client.get(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions/{session_id}",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["id"] == session_id
    assert data["topic"] == "Tech stack decision"
    assert data["transcript"] == []


@pytest.mark.asyncio
async def test_stop_session(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions",
        json={
            "topic": "Pricing strategy",
            "rounds_config": 1,
            "agents": [_adhoc_agent("Sales", "🎯", 0)],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions/{session_id}/stop",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_apply_tasks_with_no_output_returns_400(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions",
        json={
            "topic": "No output yet",
            "rounds_config": 1,
            "agents": [_adhoc_agent("Agent", "🤖", 0)],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    session_id = r.json()["id"]

    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/boardroom/sessions/{session_id}/apply",
        json={"task_ids": []},
        headers=headers,
    )
    assert r.status_code == 400, r.text
