from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from db.session import get_db
from models import Channel, ChannelMember, ChannelType, User
from core.auth import get_current_user
from pydantic import BaseModel
import uuid

router = APIRouter(tags=["dms"])

class CreateDMRequest(BaseModel):
    user_id: str  # the other user's ID

@router.get("/workspaces/{workspace_id}/dms")
async def list_dms(workspace_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return all DM channels the current user is a member of in this workspace."""
    # Find channels of type dm in this workspace where current user is a member
    result = await db.execute(
        select(Channel)
        .join(ChannelMember, ChannelMember.channel_id == Channel.id)
        .where(and_(
            Channel.workspace_id == uuid.UUID(workspace_id),
            Channel.type == ChannelType.dm,
            ChannelMember.user_id == current_user.id
        ))
    )
    channels = result.scalars().all()
    # For each DM, find the other member
    out = []
    for ch in channels:
        members_result = await db.execute(
            select(ChannelMember).where(ChannelMember.channel_id == ch.id)
        )
        members = members_result.scalars().all()
        other_ids = [str(m.user_id) for m in members if m.user_id != current_user.id]
        other_name = None
        if other_ids:
            u_result = await db.execute(select(User).where(User.id == uuid.UUID(other_ids[0])))
            other_user = u_result.scalar_one_or_none()
            other_name = other_user.name if other_user else None
        out.append({
            "id": str(ch.id),
            "other_user_id": other_ids[0] if other_ids else None,
            "other_user_name": other_name,
            "name": ch.name,
        })
    return out

@router.post("/workspaces/{workspace_id}/dm")
async def create_or_get_dm(workspace_id: str, body: CreateDMRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Find existing DM with the given user, or create one."""
    other_id = uuid.UUID(body.user_id)
    # Deterministic channel name
    ids = sorted([str(current_user.id), body.user_id])
    dm_name = f"dm:{ids[0]}-{ids[1]}"

    # Check if DM already exists
    result = await db.execute(
        select(Channel).where(and_(
            Channel.workspace_id == uuid.UUID(workspace_id),
            Channel.name == dm_name,
            Channel.type == ChannelType.dm,
        ))
    )
    existing = result.scalar_one_or_none()
    if existing:
        # Get other user info
        u_result = await db.execute(select(User).where(User.id == other_id))
        other_user = u_result.scalar_one_or_none()
        return {"id": str(existing.id), "other_user_id": body.user_id, "other_user_name": other_user.name if other_user else None}

    # Create new DM channel
    channel = Channel(
        workspace_id=uuid.UUID(workspace_id),
        name=dm_name,
        type=ChannelType.dm,
        created_by=current_user.id,
    )
    db.add(channel)
    await db.flush()
    # Add both members
    db.add(ChannelMember(channel_id=channel.id, user_id=current_user.id))
    db.add(ChannelMember(channel_id=channel.id, user_id=other_id))
    await db.commit()

    u_result = await db.execute(select(User).where(User.id == other_id))
    other_user = u_result.scalar_one_or_none()
    return {"id": str(channel.id), "other_user_id": body.user_id, "other_user_name": other_user.name if other_user else None}
