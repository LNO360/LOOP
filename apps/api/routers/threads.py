from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from db.session import get_db
from models import Message, User
from core.auth import get_current_user
import uuid

router = APIRouter(tags=["threads"])

@router.get("/workspaces/{workspace_id}/channels/{channel_id}/messages/{message_id}/thread")
async def list_thread(workspace_id: str, channel_id: str, message_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """List all replies in a thread."""
    result = await db.execute(
        select(Message).where(
            and_(
                Message.thread_id == uuid.UUID(message_id),
                Message.deleted_at.is_(None)
            )
        ).order_by(Message.created_at.asc())
    )
    msgs = result.scalars().all()
    return [{"id": str(m.id), "content": m.content, "author_id": str(m.author_id), "thread_id": str(m.thread_id), "created_at": m.created_at.isoformat()} for m in msgs]
