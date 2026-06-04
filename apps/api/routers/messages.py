from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from db.session import get_db
from models import Message, User, Notification, MessageReaction
from models.channel import Channel
from core.auth import get_current_user
from pydantic import BaseModel
from typing import Optional
import uuid, re
from datetime import datetime, timezone
from ws.manager import manager

router = APIRouter(tags=["messages"])


class CreateMessageRequest(BaseModel):
    content: str
    thread_id: Optional[str] = None


class EditMessageRequest(BaseModel):
    content: str


class ReactionRequest(BaseModel):
    emoji: str


def _msg_dict(m: Message, reactions: list[dict] | None = None) -> dict:
    return {
        "id": str(m.id),
        "content": m.content,
        "author_id": str(m.author_id),
        "thread_id": str(m.thread_id) if m.thread_id else None,
        "created_at": m.created_at.isoformat(),
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "reactions": reactions or [],
    }


async def _load_reactions(db: AsyncSession, message_ids: list[uuid.UUID]) -> dict[str, list[dict]]:
    """Load reactions for a list of message IDs. Returns {message_id: [{emoji, count, user_ids}]}"""
    if not message_ids:
        return {}
    result = await db.execute(
        select(
            MessageReaction.message_id,
            MessageReaction.emoji,
            MessageReaction.user_id,
        ).where(MessageReaction.message_id.in_(message_ids))
    )
    rows = result.all()
    # Group by message_id → emoji → user_ids
    data: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        mid = str(row.message_id)
        if mid not in data:
            data[mid] = {}
        if row.emoji not in data[mid]:
            data[mid][row.emoji] = []
        data[mid][row.emoji].append(str(row.user_id))

    out: dict[str, list[dict]] = {}
    for mid, emoji_map in data.items():
        out[mid] = [
            {"emoji": emoji, "count": len(uids), "user_ids": uids}
            for emoji, uids in emoji_map.items()
        ]
    return out


# ── List messages ────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/channels/{channel_id}/messages")
async def list_messages(
    workspace_id: str,
    channel_id: str,
    limit: int = 80,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message)
        .where(and_(
            Message.channel_id == uuid.UUID(channel_id),
            Message.deleted_at.is_(None),
            Message.thread_id.is_(None),   # main-channel messages only; thread replies fetched separately
        ))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    msgs = list(reversed(result.scalars().all()))
    msg_ids = [m.id for m in msgs]
    reactions = await _load_reactions(db, msg_ids)
    return [_msg_dict(m, reactions.get(str(m.id), [])) for m in msgs]


# ── Send message ─────────────────────────────────────────────

@router.post("/workspaces/{workspace_id}/channels/{channel_id}/messages")
async def send_message(
    workspace_id: str,
    channel_id: str,
    body: CreateMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = Message(
        channel_id=uuid.UUID(channel_id),
        author_id=current_user.id,
        content=body.content,
        thread_id=uuid.UUID(body.thread_id) if body.thread_id else None,
    )
    db.add(msg)
    await db.flush()

    # @mention notifications
    mentions = re.findall(r"@(\w+)", body.content)
    if mentions:
        result = await db.execute(select(User).where(User.name.in_(mentions)))
        for u in result.scalars().all():
            if u.id == current_user.id:
                continue
            notif = Notification(
                user_id=u.id,
                type="mention",
                entity_type="message",
                entity_id=msg.id,
                message=f"{current_user.name} mentioned you: {body.content[:80]}",
            )
            db.add(notif)
    await db.commit()
    await manager.broadcast(workspace_id, {"type": "message.new", "channel_id": channel_id})
    return _msg_dict(msg)


# ── Edit message ─────────────────────────────────────────────

@router.patch("/messages/{message_id}")
async def edit_message(
    message_id: str,
    body: EditMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Message).where(Message.id == uuid.UUID(message_id)))
    msg = result.scalar_one_or_none()
    if not msg or msg.author_id != current_user.id:
        raise HTTPException(403, "Cannot edit this message")
    if msg.deleted_at:
        raise HTTPException(400, "Message is deleted")
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Content cannot be empty")
    msg.content = content
    msg.edited_at = datetime.now(timezone.utc)
    channel_id = msg.channel_id
    await db.commit()
    # Look up workspace_id via Channel so we can broadcast to the right room
    ch_result = await db.execute(select(Channel.workspace_id).where(Channel.id == channel_id))
    workspace_id = ch_result.scalar_one_or_none()
    if workspace_id:
        await manager.broadcast(str(workspace_id), {"type": "message.updated", "channel_id": str(channel_id)})
    return _msg_dict(msg)


# ── Delete message ───────────────────────────────────────────

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Message).where(Message.id == uuid.UUID(message_id)))
    msg = result.scalar_one_or_none()
    if not msg or msg.author_id != current_user.id:
        raise HTTPException(403, "Cannot delete")
    channel_id = msg.channel_id
    msg.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    # Look up workspace_id via Channel so we can broadcast to the right room
    ch_result = await db.execute(select(Channel.workspace_id).where(Channel.id == channel_id))
    workspace_id = ch_result.scalar_one_or_none()
    if workspace_id:
        await manager.broadcast(str(workspace_id), {"type": "message.deleted", "channel_id": str(channel_id)})
    return {"deleted": True}


# ── Reactions ────────────────────────────────────────────────

@router.post("/messages/{message_id}/reactions")
async def add_reaction(
    message_id: str,
    body: ReactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    emoji = body.emoji.strip()[:16]
    if not emoji:
        raise HTTPException(400, "emoji required")
    mid = uuid.UUID(message_id)
    # Check message exists
    msg_check = await db.execute(select(Message.id).where(Message.id == mid))
    if not msg_check.scalar_one_or_none():
        raise HTTPException(404, "Message not found")
    # Upsert (ignore if already exists)
    existing = await db.execute(
        select(MessageReaction).where(
            MessageReaction.message_id == mid,
            MessageReaction.user_id == current_user.id,
            MessageReaction.emoji == emoji,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(MessageReaction(message_id=mid, user_id=current_user.id, emoji=emoji))
        await db.commit()
        # Look up channel_id + workspace_id to broadcast reaction update
        msg_result = await db.execute(select(Message.channel_id).where(Message.id == mid))
        channel_id = msg_result.scalar_one_or_none()
        if channel_id:
            ch_result = await db.execute(select(Channel.workspace_id).where(Channel.id == channel_id))
            workspace_id = ch_result.scalar_one_or_none()
            if workspace_id:
                await manager.broadcast(str(workspace_id), {"type": "reaction.updated", "channel_id": str(channel_id)})
    return {"ok": True}


@router.delete("/messages/{message_id}/reactions/{emoji}")
async def remove_reaction(
    message_id: str,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mid = uuid.UUID(message_id)
    await db.execute(
        delete(MessageReaction).where(
            MessageReaction.message_id == mid,
            MessageReaction.user_id == current_user.id,
            MessageReaction.emoji == emoji,
        )
    )
    await db.commit()
    # Look up channel_id + workspace_id to broadcast reaction update
    msg_result = await db.execute(select(Message.channel_id).where(Message.id == mid))
    channel_id = msg_result.scalar_one_or_none()
    if channel_id:
        ch_result = await db.execute(select(Channel.workspace_id).where(Channel.id == channel_id))
        workspace_id = ch_result.scalar_one_or_none()
        if workspace_id:
            await manager.broadcast(str(workspace_id), {"type": "reaction.updated", "channel_id": str(channel_id)})
    return {"ok": True}


# ── Pinned messages ──────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/channels/{channel_id}/pins")
async def list_pins(
    workspace_id: str,
    channel_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.channel import PinnedMessage
    result = await db.execute(
        select(PinnedMessage, Message, User.name.label("pinner_name"))
        .join(Message, Message.id == PinnedMessage.message_id)
        .join(User, User.id == PinnedMessage.pinned_by)
        .where(PinnedMessage.channel_id == uuid.UUID(channel_id))
        .order_by(PinnedMessage.pinned_at.desc())
        .limit(20)
    )
    rows = result.all()
    return [
        {
            "id": str(r.PinnedMessage.id),
            "message_id": str(r.PinnedMessage.message_id),
            "content": r.Message.content,
            "pinned_by_name": r.pinner_name,
            "pinned_at": r.PinnedMessage.pinned_at.isoformat(),
        }
        for r in rows
        if not r.Message.deleted_at
    ]


@router.post("/messages/{message_id}/pin")
async def pin_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.channel import PinnedMessage
    mid = uuid.UUID(message_id)
    msg_result = await db.execute(select(Message).where(Message.id == mid))
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    # Check not already pinned
    existing = await db.execute(
        select(PinnedMessage).where(
            PinnedMessage.channel_id == msg.channel_id,
            PinnedMessage.message_id == mid,
        )
    )
    if not existing.scalar_one_or_none():
        db.add(PinnedMessage(channel_id=msg.channel_id, message_id=mid, pinned_by=current_user.id))
        await db.commit()
    return {"pinned": True}


@router.delete("/messages/{message_id}/pin")
async def unpin_message(
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models.channel import PinnedMessage
    from sqlalchemy import delete as sa_delete
    mid = uuid.UUID(message_id)
    msg_result = await db.execute(select(Message.channel_id).where(Message.id == mid))
    channel_id = msg_result.scalar_one_or_none()
    if channel_id:
        await db.execute(
            sa_delete(PinnedMessage).where(
                PinnedMessage.channel_id == channel_id,
                PinnedMessage.message_id == mid,
            )
        )
        await db.commit()
    return {"unpinned": True}


# ── Thread replies ───────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/channels/{channel_id}/messages/{message_id}/thread")
async def get_thread(
    workspace_id: str,
    channel_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message)
        .where(and_(
            Message.thread_id == uuid.UUID(message_id),
            Message.deleted_at.is_(None),
        ))
        .order_by(Message.created_at.asc())
    )
    msgs = result.scalars().all()
    msg_ids = [m.id for m in msgs]
    reactions = await _load_reactions(db, msg_ids)
    return [_msg_dict(m, reactions.get(str(m.id), [])) for m in msgs]
