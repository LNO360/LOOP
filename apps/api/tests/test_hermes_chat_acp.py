"""Endpoint tests for the ACP-backed Hermes chat: conversations CRUD + SSE streaming.

The ACP engine is mocked so no real Hermes process / LLM call is made.
"""
import json
import uuid

import pytest
from httpx import AsyncClient

import routers.hermes_chat as hermes_chat
from core.acp_engine import AcpEvent


class _FakeClient:
    def __init__(self):
        self.session_id = "fake-session-123"
        self.current_model_id = None

    async def set_model(self, model_id):
        self.current_model_id = model_id

    async def prompt(self, text):
        yield AcpEvent("connecting")
        yield AcpEvent("text_delta", text="Hello ")
        yield AcpEvent("tool_start", tool_id="t1", name="lno_list_tasks")
        yield AcpEvent("tool_end", tool_id="t1", name="lno_list_tasks", status="done")
        yield AcpEvent("text_delta", text="world")
        yield AcpEvent("title", title="Greeting chat")
        yield AcpEvent("done", stop_reason="end_turn", usage={"totalTokens": 5})


class _NoTitleClient:
    def __init__(self):
        self.session_id = "fake-session-456"
        self.current_model_id = None

    async def set_model(self, model_id):
        self.current_model_id = model_id

    async def prompt(self, text):
        yield AcpEvent("text_delta", text="ok")
        yield AcpEvent("done", stop_reason="end_turn")


class _FakeEngine:
    def __init__(self, client_factory=_FakeClient):
        self._factory = client_factory

    async def get_or_create(self, key, hermes_session_id=None, model_id=None):
        return self._factory()

    async def drop(self, key):
        pass

    async def drop(self, key):
        pass


async def _signup(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": f"chat_{uuid.uuid4().hex[:8]}@test.com",
        "password": "pass123",
        "name": "Chat Tester",
        "workspace_name": f"Chat Corp {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200, resp.text
    d = resp.json()
    return d["token"], d["workspace_id"]


def _parse_sse(text: str) -> list[dict]:
    out = []
    for block in text.split("\n\n"):
        line = block.strip()
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


@pytest.mark.asyncio
async def test_conversation_lifecycle_and_streaming(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(hermes_chat, "get_engine", lambda: _FakeEngine())
    token, ws = await _signup(client)
    h = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/workspaces/{ws}/hermes/conversations"

    # create
    r = await client.post(base, json={}, headers=h)
    assert r.status_code == 200, r.text
    cid = r.json()["conversation"]["id"]

    # stream a turn
    r = await client.post(f"{base}/{cid}/chat", json={"message": "hi there"}, headers=h)
    assert r.status_code == 200, r.text
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "text_delta" in types and "tool_start" in types and "done" in types
    assert events[-1]["done"] is True

    # conversation now has user + assistant messages, title persisted
    r = await client.get(f"{base}/{cid}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant"]
    assert body["messages"][1]["content"] == "Hello world"
    assert body["messages"][1]["tool_calls"][0]["name"] == "lno_list_tasks"
    assert body["conversation"]["title"] == "Greeting chat"

    # list shows it
    r = await client.get(base, headers=h)
    assert any(c["id"] == cid for c in r.json()["conversations"])

    # delete (archive) → no longer listed
    r = await client.delete(f"{base}/{cid}", headers=h)
    assert r.status_code == 200
    r = await client.get(base, headers=h)
    assert not any(c["id"] == cid for c in r.json()["conversations"])


@pytest.mark.asyncio
async def test_title_falls_back_to_first_message(client: AsyncClient, monkeypatch):
    """When Hermes emits no title event, the conversation title falls back to the user message."""
    monkeypatch.setattr(hermes_chat, "get_engine", lambda: _FakeEngine(_NoTitleClient))
    token, ws = await _signup(client)
    h = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/workspaces/{ws}/hermes/conversations"

    cid = (await client.post(base, json={}, headers=h)).json()["conversation"]["id"]
    await client.post(f"{base}/{cid}/chat", json={"message": "Plan the Q3 roadmap please"}, headers=h)

    r = await client.get(f"{base}/{cid}", headers=h)
    assert r.json()["conversation"]["title"] == "Plan the Q3 roadmap please"
