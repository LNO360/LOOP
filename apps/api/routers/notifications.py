from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from db.session import get_db
from models import Notification, User
from core.auth import get_current_user
import uuid

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("")
async def list_notifications(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(Notification).where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc()).limit(50)
    )
    notifs = result.scalars().all()
    unread = sum(1 for n in notifs if not n.read)
    return {
        "notifications": [{"id": str(n.id), "type": n.type, "message": n.message, "read": n.read, "entity_type": n.entity_type, "entity_id": str(n.entity_id), "created_at": n.created_at.isoformat()} for n in notifs],
        "unread_count": unread
    }

@router.patch("/{notification_id}/read")
async def mark_read(notification_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(update(Notification).where(Notification.id == uuid.UUID(notification_id), Notification.user_id == current_user.id).values(read=True))
    await db.commit()
    return {"read": True}

@router.patch("/read-all")
async def mark_all_read(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await db.execute(update(Notification).where(Notification.user_id == current_user.id).values(read=True))
    await db.commit()
    return {"read": True}
