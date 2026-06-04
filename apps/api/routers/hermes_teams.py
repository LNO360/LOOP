"""
Agent team management for Hermes.

Routes:
  GET    /workspaces/{id}/hermes/teams                        — list teams with members
  POST   /workspaces/{id}/hermes/teams                        — create team
  GET    /workspaces/{id}/hermes/teams/{team_id}              — get one team
  PUT    /workspaces/{id}/hermes/teams/{team_id}              — partial update
  DELETE /workspaces/{id}/hermes/teams/{team_id}              — delete team
  POST   /workspaces/{id}/hermes/teams/{team_id}/members      — add member
  DELETE /workspaces/{id}/hermes/teams/{team_id}/members/{agent_id} — remove member
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from db.session import get_db
from models.agent import AgentTeam, AgentTeamMember, TeamRole, UserAgent

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}",
    tags=["hermes-teams"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateTeamRequest(BaseModel):
    name: str
    description: Optional[str] = None
    goal: Optional[str] = None


class UpdateTeamRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    goal: Optional[str] = None


class AddMemberRequest(BaseModel):
    agent_id: uuid.UUID
    team_role: TeamRole = TeamRole.specialist


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_team_or_404(
    db: AsyncSession, workspace_id: str, team_id: uuid.UUID
) -> AgentTeam:
    team = await db.get(AgentTeam, team_id)
    if not team or str(team.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


async def _team_to_dict(db: AsyncSession, team: AgentTeam) -> dict:
    result = await db.execute(
        select(AgentTeamMember, UserAgent)
        .join(UserAgent, AgentTeamMember.agent_id == UserAgent.id)
        .where(AgentTeamMember.team_id == team.id)
    )
    rows = result.all()
    return {
        "id": str(team.id),
        "name": team.name,
        "description": team.description,
        "goal": team.goal,
        "created_at": team.created_at.isoformat(),
        "members": [
            {
                "agent_id": str(m.agent_id),
                "agent_name": a.name,
                "agent_slug": a.slug,
                "avatar_emoji": a.avatar_emoji,
                "team_role": m.team_role.value,
            }
            for m, a in rows
        ],
    }


# ── List teams ────────────────────────────────────────────────────────────────

@router.get("/hermes/teams")
async def list_teams(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all agent teams for the workspace, with their members."""
    result = await db.execute(
        select(AgentTeam)
        .where(AgentTeam.workspace_id == uuid.UUID(workspace_id))
        .order_by(AgentTeam.created_at.asc())
    )
    teams = result.scalars().all()

    team_list = []
    for team in teams:
        team_list.append(await _team_to_dict(db, team))

    return {"teams": team_list}


# ── Create team ───────────────────────────────────────────────────────────────

@router.post("/hermes/teams")
async def create_team(
    workspace_id: str,
    body: CreateTeamRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Create a new agent team."""
    team = AgentTeam(
        workspace_id=uuid.UUID(workspace_id),
        name=body.name,
        description=body.description,
        goal=body.goal,
    )
    db.add(team)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Team already exists or constraint violation")
    await db.refresh(team)

    return {"team": await _team_to_dict(db, team)}


# ── Get team ──────────────────────────────────────────────────────────────────

@router.get("/hermes/teams/{team_id}")
async def get_team(
    workspace_id: str,
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a single agent team by ID."""
    team = await _get_team_or_404(db, workspace_id, team_id)
    return {"team": await _team_to_dict(db, team)}


# ── Update team ───────────────────────────────────────────────────────────────

@router.put("/hermes/teams/{team_id}")
async def update_team(
    workspace_id: str,
    team_id: uuid.UUID,
    body: UpdateTeamRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Partially update a team (only non-null fields are applied)."""
    team = await _get_team_or_404(db, workspace_id, team_id)

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(team, field, val)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Team already exists or constraint violation")
    await db.refresh(team)

    return {"team": await _team_to_dict(db, team)}


# ── Delete team ───────────────────────────────────────────────────────────────

@router.delete("/hermes/teams/{team_id}")
async def delete_team(
    workspace_id: str,
    team_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a team. DB CASCADE removes AgentTeamMember rows automatically."""
    team = await _get_team_or_404(db, workspace_id, team_id)
    await db.delete(team)
    await db.commit()
    return {"ok": True}


# ── Add member ────────────────────────────────────────────────────────────────

@router.post("/hermes/teams/{team_id}/members")
async def add_member(
    workspace_id: str,
    team_id: uuid.UUID,
    body: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Add an agent to a team. Agent must belong to the same workspace."""
    team = await _get_team_or_404(db, workspace_id, team_id)

    # Verify agent belongs to this workspace
    agent = await db.get(UserAgent, body.agent_id)
    if not agent or str(agent.workspace_id) != workspace_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    member = AgentTeamMember(
        team_id=team.id,
        agent_id=agent.id,
        team_role=body.team_role,
    )
    db.add(member)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Agent already in this team")

    return {"ok": True}


# ── Remove member ─────────────────────────────────────────────────────────────

@router.delete("/hermes/teams/{team_id}/members/{agent_id}")
async def remove_member(
    workspace_id: str,
    team_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove an agent from a team."""
    # Verify team exists and belongs to this workspace
    team = await _get_team_or_404(db, workspace_id, team_id)

    result = await db.execute(
        select(AgentTeamMember).where(
            AgentTeamMember.team_id == team.id,
            AgentTeamMember.agent_id == agent_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in team")

    await db.delete(member)
    await db.commit()
    return {"ok": True}
