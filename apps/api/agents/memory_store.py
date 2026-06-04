"""
Async DB helpers for workspace memory CRUD.
All functions accept an AsyncSession and workspace_id (UUID or str).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from models.other import WorkspaceMemory
import uuid
import logging

logger = logging.getLogger(__name__)


def _ws_uuid(workspace_id) -> uuid.UUID:
    return uuid.UUID(str(workspace_id)) if not isinstance(workspace_id, uuid.UUID) else workspace_id


async def get_memories(db: AsyncSession, workspace_id, limit: int = 30) -> list[dict]:
    """Fetch top memories by importance, most recent updated first."""
    ws_id = _ws_uuid(workspace_id)
    result = await db.execute(
        select(WorkspaceMemory)
        .where(WorkspaceMemory.workspace_id == ws_id)
        .order_by(WorkspaceMemory.importance.desc(), WorkspaceMemory.updated_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "key": m.key,
            "content": m.content,
            "importance": m.importance,
            "source": m.source,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
        for m in rows
    ]


async def upsert_memories(
    db: AsyncSession,
    workspace_id,
    memories: list[dict],
    source: str = "ai",
) -> int:
    """
    Insert or update memories by (workspace_id, key).
    Returns count of upserted rows.
    """
    if not memories:
        return 0
    from core.embeddings import aembed_text, memory_embedding_input

    ws_id = _ws_uuid(workspace_id)
    count = 0
    for m in memories:
        key = m.get("key", "").strip()
        content = m.get("content", "").strip()
        if not key or not content:
            continue
        # Best-effort embedding for semantic search (None if unavailable).
        embedding = await aembed_text(memory_embedding_input(key, content))
        # Check if exists
        existing = await db.execute(
            select(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == ws_id,
                WorkspaceMemory.key == key,
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.content = content
            row.importance = max(1, min(5, int(m.get("importance", row.importance))))
            row.source = source
            if embedding is not None:
                row.embedding = embedding
        else:
            db.add(WorkspaceMemory(
                workspace_id=ws_id,
                key=key,
                content=content,
                importance=max(1, min(5, int(m.get("importance", 3)))),
                source=source,
                embedding=embedding,
            ))
        count += 1
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"[memory_store] upsert failed: {e}")
        return 0
    return count


async def delete_memory(db: AsyncSession, workspace_id, memory_id: str) -> bool:
    """Delete a single memory by id, scoped to workspace."""
    ws_id = _ws_uuid(workspace_id)
    try:
        mem_id = uuid.UUID(memory_id)
    except ValueError:
        return False
    result = await db.execute(
        delete(WorkspaceMemory).where(
            WorkspaceMemory.workspace_id == ws_id,
            WorkspaceMemory.id == mem_id,
        )
    )
    await db.commit()
    return result.rowcount > 0
