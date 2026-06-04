"""Tests for hermes_teams CRUD router.

Covers:
  - GET  /teams           — empty list on fresh workspace
  - POST /teams           — create team returns full dict
  - GET  /teams/{id}      — fetch one team
  - PUT  /teams/{id}      — partial update (only changed fields)
  - POST /teams/{id}/members        — add member
  - POST /teams/{id}/members (dup)  — 409 on duplicate
  - DELETE /teams/{id}/members/{agent_id} — remove member
  - DELETE /teams/{id}    — delete team → 404 on subsequent GET
"""
import uuid
import pytest
from httpx import AsyncClient


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


async def _signup_and_auth(client: AsyncClient) -> tuple[str, str]:
    """Sign up a fresh user and return (token, workspace_id)."""
    resp = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("teamtest"),
        "password": "pass123",
        "name": "Team Tester",
        "workspace_name": f"Teams Corp {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["token"], data["workspace_id"]


async def _create_agent(client: AsyncClient, token: str, workspace_id: str) -> str:
    """Create a UserAgent in the workspace and return its id."""
    resp = await client.post(
        f"/api/v1/workspaces/{workspace_id}/hermes/agents",
        json={
            "name": f"Agent {uuid.uuid4().hex[:6]}",
            "slug": f"agent-{uuid.uuid4().hex[:6]}",
            "soul_md": "You are a test agent.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["agent"]["id"]


def _teams_url(workspace_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/hermes/teams"


def _team_url(workspace_id: str, team_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/hermes/teams/{team_id}"


def _members_url(workspace_id: str, team_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/hermes/teams/{team_id}/members"


def _member_url(workspace_id: str, team_id: str, agent_id: str) -> str:
    return f"/api/v1/workspaces/{workspace_id}/hermes/teams/{team_id}/members/{agent_id}"


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_teams_empty(client):
    """Fresh workspace has no teams."""
    token, workspace_id = await _signup_and_auth(client)
    resp = await client.get(
        _teams_url(workspace_id),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"teams": []}


@pytest.mark.asyncio
async def test_create_team(client):
    """POST /teams returns a team dict with id, name, and empty members list."""
    token, workspace_id = await _signup_and_auth(client)
    resp = await client.post(
        _teams_url(workspace_id),
        json={"name": "Alpha Squad", "description": "First team", "goal": "Win"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    team = resp.json()["team"]
    assert team["name"] == "Alpha Squad"
    assert team["description"] == "First team"
    assert team["goal"] == "Win"
    assert "id" in team
    assert team["members"] == []


@pytest.mark.asyncio
async def test_get_team(client):
    """GET /teams/{id} returns the previously created team."""
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        _teams_url(workspace_id),
        json={"name": "Bravo Team"},
        headers=headers,
    )
    team_id = create_resp.json()["team"]["id"]

    get_resp = await client.get(
        _team_url(workspace_id, team_id),
        headers=headers,
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()["team"]
    assert fetched["id"] == team_id
    assert fetched["name"] == "Bravo Team"


@pytest.mark.asyncio
async def test_partial_update_team(client):
    """PUT /teams/{id} with only name changes name; description and goal are preserved."""
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await client.post(
        _teams_url(workspace_id),
        json={"name": "Old Name", "description": "Keep this", "goal": "Also keep"},
        headers=headers,
    )
    team_id = create_resp.json()["team"]["id"]

    update_resp = await client.put(
        _team_url(workspace_id, team_id),
        json={"name": "New Name"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()["team"]
    assert updated["name"] == "New Name"
    assert updated["description"] == "Keep this"
    assert updated["goal"] == "Also keep"


@pytest.mark.asyncio
async def test_add_member(client):
    """POST /teams/{id}/members adds an agent; the team member list grows to 1."""
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    team_id = (await client.post(
        _teams_url(workspace_id),
        json={"name": "Charlie Team"},
        headers=headers,
    )).json()["team"]["id"]

    agent_id = await _create_agent(client, token, workspace_id)

    add_resp = await client.post(
        _members_url(workspace_id, team_id),
        json={"agent_id": agent_id, "team_role": "specialist"},
        headers=headers,
    )
    assert add_resp.status_code == 200
    assert add_resp.json() == {"ok": True}

    # Confirm member appears in team listing
    team_resp = await client.get(
        _team_url(workspace_id, team_id),
        headers=headers,
    )
    members = team_resp.json()["team"]["members"]
    assert len(members) == 1
    assert members[0]["agent_id"] == agent_id
    assert members[0]["team_role"] == "specialist"


@pytest.mark.asyncio
async def test_add_member_duplicate_returns_409(client):
    """Adding the same agent twice to a team returns 409."""
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    team_id = (await client.post(
        _teams_url(workspace_id),
        json={"name": "Delta Team"},
        headers=headers,
    )).json()["team"]["id"]

    agent_id = await _create_agent(client, token, workspace_id)

    payload = {"agent_id": agent_id, "team_role": "coordinator"}

    first = await client.post(_members_url(workspace_id, team_id), json=payload, headers=headers)
    assert first.status_code == 200

    second = await client.post(_members_url(workspace_id, team_id), json=payload, headers=headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_remove_member(client):
    """DELETE /teams/{id}/members/{agent_id} removes the member; list goes back to 0."""
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    team_id = (await client.post(
        _teams_url(workspace_id),
        json={"name": "Echo Team"},
        headers=headers,
    )).json()["team"]["id"]

    agent_id = await _create_agent(client, token, workspace_id)

    await client.post(
        _members_url(workspace_id, team_id),
        json={"agent_id": agent_id},
        headers=headers,
    )

    del_resp = await client.delete(
        _member_url(workspace_id, team_id, agent_id),
        headers=headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True}

    # Member list should be empty again
    team_resp = await client.get(
        _team_url(workspace_id, team_id),
        headers=headers,
    )
    assert team_resp.json()["team"]["members"] == []


@pytest.mark.asyncio
async def test_delete_team(client):
    """DELETE /teams/{id} removes the team; subsequent GET returns 404."""
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}

    team_id = (await client.post(
        _teams_url(workspace_id),
        json={"name": "Foxtrot Team"},
        headers=headers,
    )).json()["team"]["id"]

    del_resp = await client.delete(
        _team_url(workspace_id, team_id),
        headers=headers,
    )
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True}

    get_resp = await client.get(
        _team_url(workspace_id, team_id),
        headers=headers,
    )
    assert get_resp.status_code == 404
