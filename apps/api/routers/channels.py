from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from db.session import get_db
from models import Channel, ChannelMember, ChannelType, User
from core.auth import get_current_user
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/workspaces/{workspace_id}/channels", tags=["channels"])

class CreateChannelRequest(BaseModel):
    name: str
    type: str = "public"

@router.get("")
async def list_channels(workspace_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Channel).where(
        and_(
            Channel.workspace_id == uuid.UUID(workspace_id),
            Channel.type != ChannelType.dm,
        )
    ))
    channels = result.scalars().all()
    return [{"id": str(c.id), "name": c.name, "type": c.type} for c in channels]

@router.post("")
async def create_channel(workspace_id: str, body: CreateChannelRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    channel = Channel(workspace_id=uuid.UUID(workspace_id), name=body.name, type=ChannelType(body.type), created_by=current_user.id)
    db.add(channel)
    await db.flush()
    member = ChannelMember(channel_id=channel.id, user_id=current_user.id)
    db.add(member)
    await db.commit()
    return {"id": str(channel.id), "name": channel.name, "type": channel.type}
