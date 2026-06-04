"""
Workspace intelligence — health score, risk signals, suggested prompts.

Pure data analysis (no LLM). Used by REST /intelligence and MCP lno_get_workspace_intelligence.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Task, Project, TaskStatus, TaskPriority
from models.agent import ProposedAction


async def compute_workspace_intelligence(db: AsyncSession, workspace_id: uuid.UUID) -> dict:
    """Return health_score, risk_signals, suggested_prompts, and stats for a workspace."""
    today = date.today()
    week_ahead = today + timedelta(days=7)

    task_result = await db.execute(select(Task).where(Task.workspace_id == workspace_id))
    all_tasks = task_result.scalars().all()

    project_result = await db.execute(select(Project).where(Project.workspace_id == workspace_id))
    all_projects = project_result.scalars().all()

    action_result = await db.execute(
        select(ProposedAction).where(
            ProposedAction.workspace_id == workspace_id,
            ProposedAction.status == "pending",
        )
    )
    pending_actions = action_result.scalars().all()

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
    active_projects = [p for p in all_projects if p.status == "active"]

    score = 100
    score -= min(5 * len(overdue_tasks), 30)
    score -= min(10 * len(at_risk_projects), 30)
    score -= min(5 * len(unassigned_high), 20)
    if len(pending_actions) > 3:
        score -= 10
    score = max(0, score)

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

    return {
        "health_score": score,
        "risk_signals": signals,
        "suggested_prompts": prompts[:4],
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
