"""
Workspace intelligence endpoint — fast data analysis, no LLM.

GET /api/v1/workspaces/{workspace_id}/intelligence
  → health_score (0-100), risk_signals[], suggested_prompts[], stats{}

Called by the frontend on page load to drive context-aware quick prompts
and the AI insights strip. Cached 5 min on the client.
"""
import uuid
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from db.session import get_db
from models import Task, Project, TaskStatus, TaskPriority
from models.agent import ProposedAction
from models.workspace import WorkspaceMember

router = APIRouter(
    prefix="/api/v1/workspaces/{workspace_id}",
    tags=["intelligence"],
)


class IntelligenceStats(BaseModel):
    open_tasks: int
    overdue_tasks: int
    urgent_tasks: int
    this_week_tasks: int
    unassigned_high_tasks: int
    total_projects: int
    active_projects: int
    at_risk_projects: int
    pending_actions: int


class IntelligenceResponse(BaseModel):
    health_score: int
    risk_signals: list[str]
    suggested_prompts: list[str]
    stats: IntelligenceStats


@router.get("/intelligence", response_model=IntelligenceResponse)
async def get_workspace_intelligence(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Compute a workspace health score, risk signals, and suggested AI prompts.
    Pure data analysis — no Hermes/LLM call. Returns in <100ms.
    """
    # Critical 1: validate UUID format
    try:
        ws_uuid = uuid.UUID(workspace_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="workspace_id is not a valid UUID")

    # Critical 2: workspace-membership authorization (IDOR guard)
    membership = await db.execute(
        select(WorkspaceMember).where(
            and_(
                WorkspaceMember.workspace_id == ws_uuid,
                WorkspaceMember.user_id == current_user.id,
            )
        )
    )
    if not membership.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    today = date.today()
    week_ahead = today + timedelta(days=7)

    # ── Load data ────────────────────────────────────────────────────────────
    task_result = await db.execute(
        select(Task).where(Task.workspace_id == ws_uuid)
    )
    all_tasks = task_result.scalars().all()

    project_result = await db.execute(
        select(Project).where(Project.workspace_id == ws_uuid)
    )
    all_projects = project_result.scalars().all()

    action_result = await db.execute(
        select(ProposedAction).where(
            ProposedAction.workspace_id == ws_uuid,
            ProposedAction.status == "pending",
        )
    )
    pending_actions = action_result.scalars().all()

    # ── Derived counts ───────────────────────────────────────────────────────
    open_tasks = [
        t for t in all_tasks
        if t.status not in (TaskStatus.done, TaskStatus.cancelled)
    ]
    overdue_tasks = [
        t for t in open_tasks
        if t.due_date and t.due_date < today
    ]
    this_week_tasks = [
        t for t in open_tasks
        if t.due_date and today <= t.due_date <= week_ahead
    ]
    urgent_tasks = [
        t for t in open_tasks
        if t.priority in (TaskPriority.urgent, TaskPriority.high)
    ]
    unassigned_high = [
        t for t in open_tasks
        if t.priority in (TaskPriority.urgent, TaskPriority.high)
        and t.assignee_id is None
    ]

    at_risk_projects = [p for p in all_projects if p.status == "at_risk"]
    active_projects  = [p for p in all_projects if p.status == "active"]

    # ── Health score ─────────────────────────────────────────────────────────
    score = 100
    score -= min(5 * len(overdue_tasks), 30)       # -5 per overdue, cap -30
    score -= min(10 * len(at_risk_projects), 30)   # -10 per at-risk, cap -30
    score -= min(5 * len(unassigned_high), 20)     # -5 per unassigned high, cap -20
    if len(pending_actions) > 3:
        score -= 10                                # approval backlog
    score = max(0, score)

    # ── Risk signals ──────────────────────────────────────────────────────────
    signals: list[str] = []
    if overdue_tasks:
        n = len(overdue_tasks)
        signals.append(f"🔴 {n} task{'s are' if n > 1 else ' is'} overdue")
    if at_risk_projects:
        n = len(at_risk_projects)
        signals.append(f"⚠️ {n} project{'s are' if n > 1 else ' is'} at risk")
    if unassigned_high:
        n = len(unassigned_high)
        signals.append(
            f"👤 {n} high-priority task{'s have' if n > 1 else ' has'} no assignee"
        )
    if pending_actions:
        n = len(pending_actions)
        signals.append(
            f"⏳ {n} AI action{'s await' if n > 1 else ' awaits'} your approval"
        )

    # ── Suggested prompts ────────────────────────────────────────────────────
    prompts: list[str] = []

    if overdue_tasks:
        prompts.append(
            f"Review the {len(overdue_tasks)} overdue tasks and suggest next steps"
        )
    if at_risk_projects:
        prompts.append(
            f"Analyze the {len(at_risk_projects)} at-risk project{'s' if len(at_risk_projects) > 1 else ''} and propose recovery plans"
        )
    if pending_actions:
        prompts.append(
            f"Summarize the {len(pending_actions)} pending AI actions and help me decide"
        )
    if urgent_tasks:
        prompts.append(
            f"List the {len(urgent_tasks)} urgent tasks and recommend who should own them"
        )

    # Fallback defaults fill remaining slots
    defaults = [
        "Run a full workspace health check",
        "Draft a leadership status update",
        "What's blocked across all projects?",
        "Show me team workload distribution this week",
    ]
    for d in defaults:
        if len(prompts) >= 4:
            break
        if d not in prompts:
            prompts.append(d)

    prompts = prompts[:4]

    return {
        "health_score": score,
        "risk_signals": signals,
        "suggested_prompts": prompts,
        "stats": {
            "open_tasks": len(open_tasks),
            "overdue_tasks": len(overdue_tasks),
            "urgent_tasks": len(urgent_tasks),
            "this_week_tasks": len(this_week_tasks),
            "unassigned_high_tasks": len(unassigned_high),
            "total_projects": len(all_projects),
            "active_projects": len(active_projects),
            "at_risk_projects": len(at_risk_projects),
            "pending_actions": len(pending_actions),
        },
    }
