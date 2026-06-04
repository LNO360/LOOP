"""
MCP tools for structured feedback to Hermes.

lno_submit_feedback — the user (or Hermes itself) records guidance.
lno_get_feedback    — Hermes reads accumulated feedback (e.g. at session start)
                      to self-correct.

Feedback rides on WorkspaceMemory: each entry is a row keyed
"hermes.feedback.<type>.<ms>.<rand>" (per-entry, so history is preserved),
importance 4, source "feedback".
"""
import time
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.session import AsyncSessionLocal
from models.other import WorkspaceMemory
from mcp_server.server import mcp, agent_broadcast

FEEDBACK_KEY_PREFIX = "hermes.feedback."
VALID_FEEDBACK_TYPES = {"correction", "preference", "accuracy", "speed"}


def _parse_feedback_key(key: str) -> tuple[str, int]:
    """Return (type, ms) parsed from a hermes.feedback.<type>.<ms>.<rand> key."""
    parts = key.split(".")
    # ["hermes", "feedback", <type>, <ms>, <rand>]
    ftype = parts[2] if len(parts) > 2 else ""
    try:
        ms = int(parts[3]) if len(parts) > 3 else 0
    except ValueError:
        ms = 0
    return ftype, ms


@mcp.tool()
async def lno_submit_feedback(workspace_id: str, feedback_type: str, content: str) -> dict:
    """
    Record a piece of feedback for Hermes to learn from.

    feedback_type: one of "correction", "preference", "accuracy", "speed".
    content: the feedback text.

    Returns: {"ok": true, "key": "hermes.feedback.<type>.<ms>.<rand>"}
             or {"ok": false, "error": "..."} on invalid type / empty content.
    """
    feedback_type = (feedback_type or "").strip().lower()
    if feedback_type not in VALID_FEEDBACK_TYPES:
        return {"ok": False, "error": f"invalid feedback_type '{feedback_type}' "
                f"(use one of {sorted(VALID_FEEDBACK_TYPES)})"}
    content = (content or "").strip()
    if not content:
        return {"ok": False, "error": "content must not be empty"}

    key = f"{FEEDBACK_KEY_PREFIX}{feedback_type}.{int(time.time() * 1000)}.{uuid.uuid4().hex[:4]}"

    async with AsyncSessionLocal() as db:
        await db.execute(pg_insert(WorkspaceMemory).values(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(workspace_id),
            key=key,
            content=content,
            importance=4,
            source="feedback",
        ))
        await db.commit()

    await agent_broadcast(workspace_id, "lno_submit_feedback", "done",
                          f"Feedback recorded ({feedback_type})")
    return {"ok": True, "key": key}


@mcp.tool()
async def lno_get_feedback(workspace_id: str, feedback_type: str | None = None) -> dict:
    """
    Read accumulated feedback, newest first. Call at session start to self-correct.

    feedback_type: optional filter — one of "correction", "preference",
                   "accuracy", "speed". Omit to get all.

    Returns: {"ok": true, "feedback": [{"type", "content", "ts", "key"}], "total": n}
    """
    prefix = FEEDBACK_KEY_PREFIX
    if feedback_type:
        feedback_type = feedback_type.strip().lower()
        if feedback_type not in VALID_FEEDBACK_TYPES:
            return {"ok": False, "error": f"invalid feedback_type '{feedback_type}'"}
        prefix = f"{FEEDBACK_KEY_PREFIX}{feedback_type}."

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMemory.key.like(prefix + "%"),
            )
        )).scalars().all()

    items = []
    for r in rows:
        ftype, ms = _parse_feedback_key(r.key)
        items.append({"type": ftype, "content": r.content, "ts": ms, "key": r.key})
    items.sort(key=lambda x: x["ts"], reverse=True)

    return {"ok": True, "feedback": items, "total": len(items)}
