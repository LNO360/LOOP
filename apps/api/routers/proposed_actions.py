"""
Proposed Actions router — human review and execution of Hermes-proposed writes.

GET  /workspaces/{workspace_id}/proposed-actions                    — list (filter by status)
POST /workspaces/{workspace_id}/proposed-actions/{id}/approve  — approve + execute
POST /workspaces/{workspace_id}/proposed-actions/{id}/reject   — reject (no execution)
GET  /workspaces/{workspace_id}/agent-runs                     — list agent run history
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models import User, Task, TaskStatus, TaskPriority, Project, Message, WorkspaceMember
from models.agent import ProposedAction, AgentRun
from core.auth import get_current_user
from core.proposed_action_exec import execute_proposed_action

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["agent"])


def _action_out(a: ProposedAction) -> dict:
    return {
        "id": str(a.id),
        "workspace_id": str(a.workspace_id),
        "run_id": str(a.run_id) if a.run_id else None,
        "action_type": a.action_type,
        "payload": a.payload,
        "risk_level": a.risk_level,
        "status": a.status,
        "proposed_at": a.proposed_at.isoformat() if a.proposed_at else None,
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "decided_by": str(a.decided_by) if a.decided_by else None,
        "execution_result": a.execution_result,
    }


@router.get("/proposed-actions")
async def list_proposed_actions(
    workspace_id: str,
    status: Optional[str] = "pending",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ProposedAction).where(ProposedAction.workspace_id == uuid.UUID(workspace_id))
    if status and status != "all":
        q = q.where(ProposedAction.status == status)
    q = q.order_by(ProposedAction.proposed_at.desc()).limit(100)
    result = await db.execute(q)
    actions = result.scalars().all()
    return {"actions": [_action_out(a) for a in actions], "count": len(actions)}


@router.post("/proposed-actions/{action_id}/approve")
async def approve_action(
    workspace_id: str,
    action_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve and execute a proposed action."""
    result = await db.execute(
        select(ProposedAction).where(
            ProposedAction.id == uuid.UUID(action_id),
            ProposedAction.workspace_id == uuid.UUID(workspace_id),
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(404, "Proposed action not found")
    if action.status != "pending":
        raise HTTPException(400, f"Action is already {action.status}")

    # Record who approved, then run via the SHARED executor so the dashboard
    # supports every action_type (gmail, calendar, finance, github, blog,
    # deletes, …) — not the stale 5-type subset this endpoint used to inline.
    action.decided_by = current_user.id
    action.decided_at = datetime.now(timezone.utc)
    try:
        execution_result = await execute_proposed_action(
            action,
            db,
            workspace_id=workspace_id,
            actor_user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        action.status = "failed"
        action.execution_result = {"error": str(e)}
        await db.commit()
        raise HTTPException(500, f"Execution failed: {e}")

    return {"ok": True, "executed": True, "result": execution_result}


@router.post("/proposed-actions/{action_id}/reject")
async def reject_action(
    workspace_id: str,
    action_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProposedAction).where(
            ProposedAction.id == uuid.UUID(action_id),
            ProposedAction.workspace_id == uuid.UUID(workspace_id),
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(404, "Proposed action not found")
    if action.status != "pending":
        raise HTTPException(400, f"Action is already {action.status}")

    action.status = "rejected"
    action.decided_by = current_user.id
    action.decided_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "rejected": True}


@router.get("/agent-status")
async def get_agent_status(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns status for all Hermes agent personas:
    - last run time and summary per agent name
    - pending proposed action count
    - total runs this week
    """
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta

    ws_uuid = uuid.UUID(workspace_id)
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    # Last run per agent name (subquery approach)
    subq = (
        select(
            AgentRun.agent_name,
            func.max(AgentRun.started_at).label("last_run_at"),
        )
        .where(AgentRun.workspace_id == ws_uuid)
        .group_by(AgentRun.agent_name)
        .subquery()
    )
    runs_result = await db.execute(
        select(AgentRun)
        .join(
            subq,
            (AgentRun.agent_name == subq.c.agent_name)
            & (AgentRun.started_at == subq.c.last_run_at),
        )
        .where(AgentRun.workspace_id == ws_uuid)
    )
    last_runs = {r.agent_name: r for r in runs_result.scalars().all()}

    # Pending action count
    pending_result = await db.execute(
        select(func.count()).where(
            ProposedAction.workspace_id == ws_uuid,
            ProposedAction.status == "pending",
        )
    )
    pending_count = pending_result.scalar() or 0

    # Total runs this week
    weekly_result = await db.execute(
        select(func.count()).where(
            AgentRun.workspace_id == ws_uuid,
            AgentRun.started_at >= week_ago,
        )
    )
    weekly_count = weekly_result.scalar() or 0

    # Known agent definitions (names match cron job names in entrypoint.sh)
    known_agents = [
        {"name": "lno-ops-monitor", "display": "Ops Monitor", "schedule": "Every 2 hours"},
        {"name": "lno-daily-digest", "display": "Daily Digest", "schedule": "8 AM daily"},
        {"name": "lno-product-manager", "display": "Product Manager", "schedule": "Mon 9 AM"},
        {"name": "lno-team-pulse", "display": "Team Pulse", "schedule": "Fri 4 PM"},
    ]

    agents_status = []
    for agent_def in known_agents:
        run = last_runs.get(agent_def["name"])
        agents_status.append({
            **agent_def,
            "last_run_at": run.started_at.isoformat() if run else None,
            "last_run_status": run.status if run else "never_run",
            "last_run_summary": run.result_summary if run else None,
            "tool_calls_count": len(run.tool_calls_json or []) if run and hasattr(run, "tool_calls_json") else 0,
        })

    return {
        "agents": agents_status,
        "pending_actions": pending_count,
        "weekly_runs": weekly_count,
    }


@router.get("/agent-memory")
async def get_agent_memory(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all workspace memories written by Hermes agents, sorted by importance."""
    from models.other import WorkspaceMemory

    result = await db.execute(
        select(WorkspaceMemory)
        .where(WorkspaceMemory.workspace_id == uuid.UUID(workspace_id))
        .order_by(WorkspaceMemory.importance.desc(), WorkspaceMemory.updated_at.desc())
        .limit(200)
    )
    return {
        "memories": [
            {
                "key": m.key,
                "content": m.content,
                "importance": m.importance,
                "source": m.source,
            }
            for m in result.scalars().all()
        ]
    }


@router.get("/agent-runs")
async def list_agent_runs(
    workspace_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.workspace_id == uuid.UUID(workspace_id))
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return {
        "runs": [
            {
                "id": str(r.id),
                "trigger_type": r.trigger_type,
                "agent_name": r.agent_name,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "result_summary": r.result_summary,
            }
            for r in runs
        ],
        "count": len(runs),
    }
