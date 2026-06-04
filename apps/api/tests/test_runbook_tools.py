"""Tests for the Hermes runbook tools (mcp_server/tools/runbook_tools.py).

A runbook is a saved JSON recipe (ordered steps). Execution returns the resolved
plan for the agent to run — it does not dispatch tools server-side.

Covers:
  - create -> list -> execute round-trip
  - invalid steps rejected (not a list / step missing "tool")
  - execute returns steps in order
  - execute on a missing runbook errors
  - execute resolves by display name as well as slug
"""
import uuid
import pytest
from httpx import AsyncClient

from mcp_server.tools import runbook_tools as rb


@pytest.fixture(autouse=True)
async def _dispose_shared_engine():
    yield
    from db.session import engine
    await engine.dispose()


async def _new_workspace(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": f"rb_{uuid.uuid4().hex[:8]}@test.com",
        "password": "pass123",
        "name": "RB Tester",
        "workspace_name": f"RB {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["workspace_id"]


_STEPS = [
    {"tool": "lno_get_workspace_snapshot", "params": {}, "note": "see state"},
    {"tool": "lno_create_task", "params": {"title": "Weekly digest"}, "note": "make task"},
]


@pytest.mark.asyncio
async def test_create_list_execute_roundtrip(client):
    ws = await _new_workspace(client)
    created = await rb.lno_create_runbook(ws, "Weekly Digest", _STEPS, description="Run the weekly digest")
    assert created["ok"] is True
    slug = created["slug"]

    listed = await rb.lno_list_runbooks(ws)
    assert listed["ok"] is True
    names = {r["name"] for r in listed["runbooks"]}
    assert "Weekly Digest" in names
    entry = next(r for r in listed["runbooks"] if r["slug"] == slug)
    assert entry["step_count"] == 2
    assert entry["description"] == "Run the weekly digest"

    run = await rb.lno_execute_runbook(ws, slug)
    assert run["ok"] is True
    assert run["name"] == "Weekly Digest"
    assert [s["tool"] for s in run["steps"]] == [
        "lno_get_workspace_snapshot", "lno_create_task"]


@pytest.mark.asyncio
async def test_invalid_steps_rejected(client):
    ws = await _new_workspace(client)
    not_a_list = await rb.lno_create_runbook(ws, "Bad One", "do stuff")
    assert not_a_list["ok"] is False

    missing_tool = await rb.lno_create_runbook(ws, "Bad Two", [{"params": {}}])
    assert missing_tool["ok"] is False
    assert "tool" in missing_tool["error"]


@pytest.mark.asyncio
async def test_execute_returns_steps_in_order(client):
    ws = await _new_workspace(client)
    steps = [{"tool": f"step_{i}"} for i in range(5)]
    created = await rb.lno_create_runbook(ws, "Ordered", steps)
    run = await rb.lno_execute_runbook(ws, created["slug"])
    assert [s["tool"] for s in run["steps"]] == [f"step_{i}" for i in range(5)]


@pytest.mark.asyncio
async def test_execute_missing_runbook_errors(client):
    ws = await _new_workspace(client)
    run = await rb.lno_execute_runbook(ws, "does-not-exist")
    assert run["ok"] is False
    assert "not found" in run["error"].lower()


@pytest.mark.asyncio
async def test_execute_resolves_by_name(client):
    ws = await _new_workspace(client)
    await rb.lno_create_runbook(ws, "Onboard Operator", _STEPS)
    run = await rb.lno_execute_runbook(ws, "Onboard Operator")
    assert run["ok"] is True
    assert run["name"] == "Onboard Operator"
