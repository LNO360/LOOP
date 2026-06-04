# apps/api/routers/invites.py
"""
Workspace invite-link system.

POST /workspaces/{id}/invite-link   — generate a shareable token (member only)
GET  /invites/{token}               — public: validate + return workspace name
POST /invites/{token}/accept        — auth required: join the workspace
"""
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.config import settings
from db.session import get_db
from models import Workspace, WorkspaceMember, MemberRole, User
from models.invite import WorkspaceInvite
import uuid

router = APIRouter(tags=["invites"])


@router.post("/workspaces/{workspace_id}/invite-link")
async def create_invite_link(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or return existing) invite link for a workspace."""
    ws_uuid = uuid.UUID(workspace_id)

    # Must be a member
    r = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws_uuid,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    if not r.scalar_one_or_none():
        raise HTTPException(403, "Not a member of this workspace")

    # Re-use an existing non-expired invite if one exists
    existing = await db.execute(
        select(WorkspaceInvite).where(
            WorkspaceInvite.workspace_id == ws_uuid,
            WorkspaceInvite.created_by == current_user.id,
        ).order_by(WorkspaceInvite.created_at.desc()).limit(1)
    )
    inv = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if inv and (inv.expires_at is None or inv.expires_at > now):
        token = inv.token
    else:
        token = secrets.token_urlsafe(24)
        inv = WorkspaceInvite(
            workspace_id=ws_uuid,
            created_by=current_user.id,
            token=token,
            expires_at=now + timedelta(days=7),
        )
        db.add(inv)
        await db.commit()

    frontend = settings.frontend_url
    return {"token": token, "url": f"{frontend}/join/{token}"}


@router.get("/invites/{token}")
async def validate_invite(token: str, db: AsyncSession = Depends(get_db)):
    """Public: return workspace name + inviter for the join page."""
    r = await db.execute(
        select(WorkspaceInvite).where(WorkspaceInvite.token == token)
    )
    inv = r.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invite link not found or expired")

    now = datetime.now(timezone.utc)
    if inv.expires_at and inv.expires_at < now:
        raise HTTPException(410, "Invite link has expired")
    if inv.max_uses and inv.use_count >= inv.max_uses:
        raise HTTPException(410, "Invite link has reached its use limit")

    ws = await db.get(Workspace, inv.workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace no longer exists")
    inviter = await db.get(User, inv.created_by) if inv.created_by else None

    return {
        "workspace_id":    str(ws.id),
        "workspace_name":  ws.name,
        "workspace_emoji": ws.emoji or "🚀",
        "inviter_name":    inviter.name if inviter else "A teammate",
    }


@router.post("/invites/{token}/accept")
async def accept_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auth required: join the workspace linked to this token."""
    r = await db.execute(
        select(WorkspaceInvite).where(WorkspaceInvite.token == token)
    )
    inv = r.scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Invite link not found")

    now = datetime.now(timezone.utc)
    if inv.expires_at and inv.expires_at < now:
        raise HTTPException(410, "Invite link has expired")

    ws = await db.get(Workspace, inv.workspace_id)
    if not ws:
        raise HTTPException(404, "Workspace no longer exists")

    # Idempotent: already a member → just return workspace_id
    existing_member = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == inv.workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    if not existing_member.scalar_one_or_none():
        db.add(WorkspaceMember(
            workspace_id=inv.workspace_id,
            user_id=current_user.id,
            role=MemberRole.member,
        ))
        inv.use_count += 1
        await db.commit()

    return {"workspace_id": str(inv.workspace_id)}
