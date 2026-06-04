from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models import Workspace, WorkspaceMember, User, MemberRole
from core.auth import get_current_user
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

class CreateWorkspaceRequest(BaseModel):
    name: str

@router.post("")
async def create_workspace(
    body: CreateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new workspace for the current user (used when joining via onboarding)."""
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Workspace name cannot be empty")
    slug = name.lower().replace(" ", "-") + "-" + str(uuid.uuid4())[:8]
    workspace = Workspace(name=name, slug=slug, owner_id=current_user.id, emoji="🚀")
    db.add(workspace)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=current_user.id, role=MemberRole.admin))
    await db.commit()
    return {"id": str(workspace.id), "name": workspace.name, "slug": workspace.slug, "emoji": workspace.emoji or "🚀"}

@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(404, "Workspace not found")
    return {"id": str(ws.id), "name": ws.name, "slug": ws.slug, "emoji": ws.emoji or "🚀"}

@router.get("/{workspace_id}/members")
async def get_members(workspace_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(
        select(User, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == uuid.UUID(workspace_id))
    )
    rows = result.all()
    return [{"id": str(u.id), "name": u.name, "email": u.email, "avatar_url": u.avatar_url, "role": r} for u, r in rows]

class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None

@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: UpdateWorkspaceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(404, "Workspace not found")
    if body.name is not None:
        ws.name = body.name.strip()
    if body.emoji is not None:
        ws.emoji = body.emoji
    await db.commit()
    return {"id": str(ws.id), "name": ws.name, "emoji": ws.emoji or "🚀"}

@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
            WorkspaceMember.user_id == uuid.UUID(user_id),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "Member not found")
    if str(member.user_id) == str(current_user.id):
        raise HTTPException(400, "Cannot remove yourself")
    await db.delete(member)
    await db.commit()
    return {"removed": True}

class InviteRequest(BaseModel):
    email: EmailStr
    role: str = "member"

@router.post("/{workspace_id}/invite")
async def invite_member(workspace_id: str, body: InviteRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found — they must sign up first")
    member = WorkspaceMember(workspace_id=uuid.UUID(workspace_id), user_id=user.id, role=MemberRole(body.role))
    db.add(member)
    await db.commit()
    return {"message": "Invited"}
