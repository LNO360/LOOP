"""
MCP tool for syncing Hermes hot memory (MEMORY.md) with warm memory (DB).

lno_sync_hermes_memory — reconcile apps/hermes-data/memories/MEMORY.md against
the WorkspaceMemory table using content-hash union-merge.

Hot memory is a keyless list of free-text blocks separated by a "§" line. Warm
memory is the keyed WorkspaceMemory table. Each hot block maps to a row keyed
"hermes.hot.<sha8>" where sha8 is the first 8 hex chars of the SHA-256 of the
block's normalized text, so upserts are idempotent and never duplicate.

Directions:
  push — file blocks -> DB (hermes.hot.*)
  pull — DB hermes.hot.* -> file
  both — union of both sides (deduped by hash) written back to both; additive,
         never loses data. Deletion is intentionally out of scope.
"""
import hashlib
import os
import re
import uuid
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.session import AsyncSessionLocal
from models.other import WorkspaceMemory
from mcp_server.server import mcp, agent_broadcast

SEPARATOR = "§"
HOT_KEY_PREFIX = "hermes.hot."

# Locally the repo root is 4 parents above this file (tools -> mcp_server -> api
# -> apps -> root). In the container the code lives at /app, which has fewer
# parents, so guard the index. Prefer the HERMES_MEMORY_MD_PATH env override
# (set in production) via _memory_md_path() below.
_PARENTS = Path(__file__).resolve().parents
_REPO_ROOT = _PARENTS[4] if len(_PARENTS) > 4 else _PARENTS[-1]
DEFAULT_MEMORY_MD_PATH = _REPO_ROOT / "apps/hermes-data/memories/MEMORY.md"

_SEPARATOR_LINE = re.compile(r"(?m)^\s*§\s*$")
_WHITESPACE = re.compile(r"\s+")


def _memory_md_path() -> Path:
    """Resolve the MEMORY.md path, honouring HERMES_MEMORY_MD_PATH for tests."""
    override = os.environ.get("HERMES_MEMORY_MD_PATH")
    return Path(override) if override else DEFAULT_MEMORY_MD_PATH


def normalize_block(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip ends."""
    return _WHITESPACE.sub(" ", text).strip()


def block_hash(text: str) -> str:
    """First 8 hex chars of SHA-256 over the normalized block text."""
    return hashlib.sha256(normalize_block(text).encode("utf-8")).hexdigest()[:8]


def parse_blocks(md: str) -> list[str]:
    """Split a MEMORY.md body into stripped, non-empty blocks on § separator lines."""
    if not md:
        return []
    return [b.strip() for b in _SEPARATOR_LINE.split(md) if b.strip()]


def render_blocks(blocks: list[str]) -> str:
    """Render blocks back to MEMORY.md form (§-separated)."""
    if not blocks:
        return ""
    return f"\n{SEPARATOR}\n".join(b.strip() for b in blocks) + "\n"


def union_merge(file_blocks: list[str], db_blocks: list[str]) -> list[str]:
    """Union of both block lists, deduped by content hash, file order first."""
    seen: set[str] = set()
    ordered: list[str] = []
    for b in list(file_blocks) + list(db_blocks):
        h = block_hash(b)
        if h not in seen:
            seen.add(h)
            ordered.append(b.strip())
    return ordered


async def _upsert_hot(db, workspace_id: str, content: str) -> None:
    """Upsert one hot block as hermes.hot.<sha8> (no commit)."""
    content = content.strip()
    stmt = pg_insert(WorkspaceMemory).values(
        id=uuid.uuid4(),
        workspace_id=uuid.UUID(str(workspace_id)),
        key=HOT_KEY_PREFIX + block_hash(content),
        content=content,
        importance=3,
        source="hermes-hot",
    ).on_conflict_do_update(
        constraint="uq_workspace_memory_key",
        set_={"content": content, "source": "hermes-hot", "updated_at": func.now()},
    )
    await db.execute(stmt)


@mcp.tool()
async def lno_sync_hermes_memory(workspace_id: str, direction: str = "both") -> dict:
    """
    Sync Hermes hot memory (MEMORY.md) with warm memory (WorkspaceMemory DB).

    direction:
      "push" — write MEMORY.md blocks into the DB (hermes.hot.*)
      "pull" — rebuild MEMORY.md from the DB hermes.hot.* rows
      "both" — union-merge both sides (deduped by content hash) and write back
               to both. Additive: never deletes a fact. (default)

    Returns: {"ok", "direction", "pushed", "pulled", "total_blocks", "hash_keys"}
    """
    direction = (direction or "both").lower()
    if direction not in ("push", "pull", "both"):
        return {"ok": False, "error": f"invalid direction '{direction}' (use push|pull|both)"}

    await agent_broadcast(workspace_id, "lno_sync_hermes_memory", "running",
                          f"Syncing hot↔warm memory ({direction})")

    path = _memory_md_path()
    file_blocks = parse_blocks(path.read_text()) if path.exists() else []

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMemory.key.like(HOT_KEY_PREFIX + "%"),
            )
        )).scalars().all()
        db_blocks = [r.content for r in rows]
        db_hashes_before = {block_hash(b) for b in db_blocks}
        file_hashes_before = {block_hash(b) for b in file_blocks}

        pushed = pulled = 0

        if direction == "push":
            final_blocks = file_blocks
            for b in final_blocks:
                await _upsert_hot(db, workspace_id, b)
            pushed = len(final_blocks)
        elif direction == "pull":
            final_blocks = db_blocks
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_blocks(final_blocks))
            pulled = len(final_blocks)
        else:  # both
            final_blocks = union_merge(file_blocks, db_blocks)
            for b in final_blocks:
                await _upsert_hot(db, workspace_id, b)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_blocks(final_blocks))
            pushed = sum(1 for b in final_blocks if block_hash(b) not in db_hashes_before)
            pulled = sum(1 for b in final_blocks if block_hash(b) not in file_hashes_before)

        await db.commit()

    hash_keys = sorted({HOT_KEY_PREFIX + block_hash(b) for b in final_blocks})
    await agent_broadcast(workspace_id, "lno_sync_hermes_memory", "done",
                          f"Memory synced ({direction}): +{pushed} to DB, +{pulled} to file, "
                          f"{len(final_blocks)} total")
    return {
        "ok": True,
        "direction": direction,
        "pushed": pushed,
        "pulled": pulled,
        "total_blocks": len(final_blocks),
        "hash_keys": hash_keys,
    }
