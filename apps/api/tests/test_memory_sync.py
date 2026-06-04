"""Tests for the Hermes memory sync tool (mcp_server/tools/memory_sync.py).

Covers:
  Pure helpers (no DB):
    - block_hash: whitespace-insensitive, stable, distinct for distinct text
    - parse_blocks: splits a MEMORY.md body on § separator lines
    - render_blocks / parse_blocks round-trip
    - union_merge: dedups by content hash, loses no data
  DB sync (lno_sync_hermes_memory), against a real workspace + tmp MEMORY.md:
    - push: file blocks land as hermes.hot.<sha8> rows
    - pull: DB hot rows rebuild the file
    - both: union-merge — neither side loses data
    - push is idempotent (no duplicate rows)
    - invalid direction is rejected
"""
import os
import uuid
import pytest
from httpx import AsyncClient

from mcp_server.tools import memory_sync as ms
from db.session import AsyncSessionLocal
from models.other import WorkspaceMemory
from sqlalchemy import select


# ── Pure helpers ──────────────────────────────────────────────────────────────

def test_block_hash_is_whitespace_insensitive_and_stable():
    h1 = ms.block_hash("hello   world")
    h2 = ms.block_hash("  hello world  ")
    h3 = ms.block_hash("hello\nworld")
    assert h1 == h2 == h3
    assert len(h1) == 8


def test_block_hash_distinct_for_distinct_text():
    assert ms.block_hash("fact A") != ms.block_hash("fact B")


def test_parse_blocks_splits_on_separator_lines():
    md = "first fact\n§\nsecond fact\n§\nthird fact\n"
    assert ms.parse_blocks(md) == ["first fact", "second fact", "third fact"]


def test_parse_blocks_empty_input():
    assert ms.parse_blocks("") == []
    assert ms.parse_blocks("\n§\n\n") == []


def test_render_parse_roundtrip():
    blocks = ["alpha fact", "beta fact", "gamma fact"]
    assert ms.parse_blocks(ms.render_blocks(blocks)) == blocks


def test_union_merge_dedups_by_hash_and_loses_nothing():
    file_blocks = ["shared fact", "file only"]
    db_blocks = ["  shared   fact  ", "db only"]  # 'shared fact' dup by hash
    merged = ms.union_merge(file_blocks, db_blocks)
    hashes = {ms.block_hash(b) for b in merged}
    # one shared + file only + db only == 3 unique
    assert len(merged) == 3
    assert ms.block_hash("shared fact") in hashes
    assert ms.block_hash("file only") in hashes
    assert ms.block_hash("db only") in hashes


# ── DB sync ───────────────────────────────────────────────────────────────────

async def _new_workspace(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": f"memsync_{uuid.uuid4().hex[:8]}@test.com",
        "password": "pass123",
        "name": "Mem Sync Tester",
        "workspace_name": f"MemSync {uuid.uuid4().hex[:6]}",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["workspace_id"]


async def _hot_rows(workspace_id: str) -> list[WorkspaceMemory]:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMemory.key.like(ms.HOT_KEY_PREFIX + "%"),
            )
        )).scalars().all()
    return list(rows)


@pytest.fixture
def tmp_memory_file(tmp_path, monkeypatch):
    path = tmp_path / "MEMORY.md"
    monkeypatch.setenv("HERMES_MEMORY_MD_PATH", str(path))
    return path


@pytest.fixture(autouse=True)
async def _dispose_shared_engine():
    """The tool uses the pooled db.session.engine directly; dispose its pool after
    each test so asyncpg connections aren't reused across the session event loop."""
    yield
    from db.session import engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_push_writes_blocks_to_db(client, tmp_memory_file):
    ws = await _new_workspace(client)
    tmp_memory_file.write_text("push fact one\n§\npush fact two\n")

    out = await ms.lno_sync_hermes_memory(ws, direction="push")
    assert out["ok"] is True
    assert out["pushed"] == 2

    contents = {r.content for r in await _hot_rows(ws)}
    assert "push fact one" in contents
    assert "push fact two" in contents


@pytest.mark.asyncio
async def test_pull_rebuilds_file_from_db(client, tmp_memory_file):
    ws = await _new_workspace(client)
    # seed DB by pushing, then wipe the file
    tmp_memory_file.write_text("seed fact A\n§\nseed fact B\n")
    await ms.lno_sync_hermes_memory(ws, direction="push")
    tmp_memory_file.write_text("")

    out = await ms.lno_sync_hermes_memory(ws, direction="pull")
    assert out["ok"] is True
    assert out["pulled"] == 2

    rebuilt = ms.parse_blocks(tmp_memory_file.read_text())
    assert set(rebuilt) == {"seed fact A", "seed fact B"}


@pytest.mark.asyncio
async def test_both_union_merge_loses_no_data(client, tmp_memory_file):
    ws = await _new_workspace(client)
    # DB gets block B via push, then file is replaced with block A only
    tmp_memory_file.write_text("only in db\n")
    await ms.lno_sync_hermes_memory(ws, direction="push")
    tmp_memory_file.write_text("only in file\n")

    out = await ms.lno_sync_hermes_memory(ws, direction="both")
    assert out["ok"] is True

    file_blocks = set(ms.parse_blocks(tmp_memory_file.read_text()))
    db_contents = {r.content for r in await _hot_rows(ws)}
    assert {"only in db", "only in file"} <= file_blocks
    assert {"only in db", "only in file"} <= db_contents


@pytest.mark.asyncio
async def test_push_is_idempotent(client, tmp_memory_file):
    ws = await _new_workspace(client)
    tmp_memory_file.write_text("idempotent fact\n§\nanother fact\n")
    await ms.lno_sync_hermes_memory(ws, direction="push")
    await ms.lno_sync_hermes_memory(ws, direction="push")
    assert len(await _hot_rows(ws)) == 2


@pytest.mark.asyncio
async def test_invalid_direction_rejected(client, tmp_memory_file):
    ws = await _new_workspace(client)
    out = await ms.lno_sync_hermes_memory(ws, direction="sideways")
    assert out["ok"] is False
    assert "direction" in out["error"].lower()
