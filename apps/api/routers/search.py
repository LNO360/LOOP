from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from db.session import get_db
from models import Task, Document, Message, User
from core.auth import get_current_user
import uuid

router = APIRouter(tags=["search"])

@router.get("/workspaces/{workspace_id}/search")
async def search(
    workspace_id: str,
    q: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not q or len(q) < 2:
        return {"tasks": [], "docs": [], "messages": []}

    ws_id = uuid.UUID(workspace_id)
    term = f"%{q}%"

    # Tasks
    task_result = await db.execute(
        select(Task).where(
            Task.workspace_id == ws_id,
            or_(Task.title.ilike(term), Task.description.ilike(term))
        ).limit(10)
    )
    tasks = [
        {"id": str(t.id), "title": t.title, "status": str(t.status), "priority": str(t.priority)}
        for t in task_result.scalars().all()
    ]

    # Documents
    doc_result = await db.execute(
        select(Document).where(
            Document.workspace_id == ws_id,
            Document.title.ilike(term)
        ).limit(5)
    )
    docs = [
        {"id": str(d.id), "title": d.title}
        for d in doc_result.scalars().all()
    ]

    # Messages (only non-deleted)
    msg_result = await db.execute(
        select(Message).where(
            Message.channel_id.in_(
                select(Message.channel_id).where(Message.deleted_at.is_(None))
            ),
            Message.content.ilike(term),
            Message.deleted_at.is_(None),
        ).limit(5)
    )
    messages = [
        {"id": str(m.id), "content": m.content[:120], "channel_id": str(m.channel_id), "created_at": m.created_at.isoformat()}
        for m in msg_result.scalars().all()
    ]

    return {"tasks": tasks, "docs": docs, "messages": messages}
