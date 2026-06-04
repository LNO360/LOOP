"""Tests for the Hermes feedback tools (mcp_server/tools/feedback_tools.py).

Covers:
  - submit stores a hermes.feedback.<type>.* row and get returns it
  - invalid feedback_type is rejected
  - get filters by type
  - get returns newest-first
  - get on a fresh workspace is empty
"""
import uuid
import pytest
from httpx import AsyncClient

from mcp_server.tools import feedback_tools as fb


@pytest.fixture(autouse=True)
async def _dispose_shared_engine():
    yield
    from db.session import engine
    await engine.dispose()


async def _new_workspace(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": f"fb_{uuid.uuid4().hex[:8]}@test.com",
        "password": "pass123",
        "name": "FB Tester",
        "workspace_name": f"FB {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["workspace_id"]


@pytest.mark.asyncio
async def test_submit_then_get_roundtrip(client):
    ws = await _new_workspace(client)
    out = await fb.lno_submit_feedback(ws, "correction", "Use IST, not UTC, for digests")
    assert out["ok"] is True
    assert out["key"].startswith("hermes.feedback.correction.")

    got = await fb.lno_get_feedback(ws)
    assert got["ok"] is True
    assert got["total"] == 1
    assert got["feedback"][0]["type"] == "correction"
    assert got["feedback"][0]["content"] == "Use IST, not UTC, for digests"


@pytest.mark.asyncio
async def test_invalid_type_rejected(client):
    ws = await _new_workspace(client)
    out = await fb.lno_submit_feedback(ws, "vibes", "be cooler")
    assert out["ok"] is False
    assert "feedback_type" in out["error"]
    # nothing stored
    got = await fb.lno_get_feedback(ws)
    assert got["total"] == 0


@pytest.mark.asyncio
async def test_get_filters_by_type(client):
    ws = await _new_workspace(client)
    await fb.lno_submit_feedback(ws, "preference", "prefer bullet points")
    await fb.lno_submit_feedback(ws, "speed", "respond faster on cron")

    only_speed = await fb.lno_get_feedback(ws, feedback_type="speed")
    assert only_speed["total"] == 1
    assert only_speed["feedback"][0]["type"] == "speed"


@pytest.mark.asyncio
async def test_get_newest_first(client):
    ws = await _new_workspace(client)
    await fb.lno_submit_feedback(ws, "accuracy", "first")
    await fb.lno_submit_feedback(ws, "accuracy", "second")

    got = await fb.lno_get_feedback(ws)
    assert [f["content"] for f in got["feedback"]] == ["second", "first"]


@pytest.mark.asyncio
async def test_get_empty_workspace(client):
    ws = await _new_workspace(client)
    got = await fb.lno_get_feedback(ws)
    assert got["ok"] is True
    assert got["total"] == 0
    assert got["feedback"] == []
