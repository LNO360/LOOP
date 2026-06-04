"""Tests for Slack-style in-channel agents (mention detection + agent-authored messages)."""
import uuid

import pytest
from httpx import AsyncClient

import core.channel_agents as ca
from core.acp_engine import AcpEvent
from db.session import AsyncSessionLocal


# ── extract_mentions (pure) ──────────────────────────────────────────────────

def test_extract_mentions_forms():
    assert ca.extract_mentions("hey @hermes and @[Research Bot]!") == ["hermes", "Research Bot"]
    assert ca.extract_mentions("no mentions here") == []
    assert ca.extract_mentions("@ops-monitor please check") == ["ops-monitor"]


# ── helpers ──────────────────────────────────────────────────────────────────

async def _signup(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": f"agent_{uuid.uuid4().hex[:8]}@test.com",
        "password": "pass123",
        "name": "Agent Tester",
        "workspace_name": f"Agent Corp {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200, resp.text
    d = resp.json()
    return d["token"], d["workspace_id"]


async def _create_agent(client, token, ws, name="Research Bot") -> str:
    r = await client.post(
        f"/api/v1/workspaces/{ws}/hermes/agents",
        json={"name": name, "soul_md": "You research things."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return r.json()["agent"]["slug"]


class _FakeClient:
    session_id = "fake-channel-session"

    async def prompt(self, text):
        yield AcpEvent("text_delta", text="On it — ")
        yield AcpEvent("text_delta", text="here's the summary.")
        yield AcpEvent("done", stop_reason="end_turn")


class _FakeEngine:
    async def get_or_create(self, key, hermes_session_id=None, model_id=None):
        return _FakeClient()


# ── resolve_mentioned_agents (DB) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolve_mentioned_agents(client: AsyncClient):
    token, ws = await _signup(client)
    slug = await _create_agent(client, token, ws)

    async with AsyncSessionLocal() as db:
        ws_uuid = uuid.UUID(ws)
        # by name
        by_name = await ca.resolve_mentioned_agents(db, ws_uuid, "ping @[Research Bot] now")
        assert any(a["slug"] == slug for a in by_name)
        # by slug
        by_slug = await ca.resolve_mentioned_agents(db, ws_uuid, f"@{slug} hello")
        assert any(a["slug"] == slug for a in by_slug)
        # hermes always available
        hermes = await ca.resolve_mentioned_agents(db, ws_uuid, "hey @hermes")
        assert any(a["slug"] == "hermes" and a["persona"] is None for a in hermes)
        # unknown → nothing
        none = await ca.resolve_mentioned_agents(db, ws_uuid, "@nobody here")
        assert none == []


# ── run_channel_agent posts a streaming agent message ────────────────────────

@pytest.mark.asyncio
async def test_run_channel_agent_posts_message(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(ca, "get_engine", lambda: _FakeEngine())
    token, ws = await _signup(client)
    h = {"Authorization": f"Bearer {token}"}

    ch = await client.post(f"/api/v1/workspaces/{ws}/channels", json={"name": "general", "type": "public"}, headers=h)
    assert ch.status_code == 200, ch.text
    channel_id = ch.json()["id"]

    await ca.run_channel_agent(
        ws, channel_id,
        {"slug": "hermes", "name": "Hermes", "persona": None},
        "hey @hermes summarize",
    )

    msgs = await client.get(f"/api/v1/workspaces/{ws}/channels/{channel_id}/messages", headers=h)
    assert msgs.status_code == 200, msgs.text
    agent_msgs = [m for m in msgs.json() if m["sender_type"] == "agent"]
    assert len(agent_msgs) == 1
    assert agent_msgs[0]["agent_slug"] == "hermes"
    assert agent_msgs[0]["author_id"] is None
    assert agent_msgs[0]["content"] == "On it — here's the summary."
