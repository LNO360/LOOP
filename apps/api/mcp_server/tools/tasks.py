"""
MCP tools for task operations.

Read tools  (execute immediately): lno_list_tasks, lno_list_overdue_tasks
Write tools (create proposed_action): lno_create_task, lno_update_task
"""
import uuid
from datetime import date, timedelta
from typing import Optional
from sqlalchemy import select, and_, or_
from db.session import AsyncSessionLocal
from models import Task, TaskStatus, TaskPriority, User, Project, TaskAssignee
from models.agent import ProposedAction
from mcp_server.server import mcp, agent_broadcast
from core.task_assignees import load_assignees_by_task, task_assignee_fields


def _enrich_task_row(row, assignee_map: dict) -> dict:
    assignees = assignee_map.get(str(row.Task.id), [])
    base = {
        "id": str(row.Task.id),
        "title": row.Task.title,
        "status": str(row.Task.status.value if hasattr(row.Task.status, "value") else row.Task.status),
        "priority": str(row.Task.priority.value if hasattr(row.Task.priority, "value") else row.Task.priority),
        "project_id": str(row.Task.project_id) if row.Task.project_id else None,
        "project_name": getattr(row, "project_name", None),
        "due_date": row.Task.due_date.isoformat() if row.Task.due_date else None,
        "created_at": row.Task.created_at.isoformat() if row.Task.created_at else None,
    }
    if assignees:
        base.update(task_assignee_fields(assignees))
    else:
        base.update({
            "assignee_ids": [],
            "assignee_names": [],
            "assignee_id": str(row.Task.assignee_id) if row.Task.assignee_id else None,
        })
        if getattr(row, "assignee_name", None):
            base["assignee_names"] = [row.assignee_name]
    return base


@mcp.tool()
async def lno_list_tasks(
    workspace_id: str,
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    assignee_id: Optional[str] = None,
    limit: int = 15,
) -> list[dict]:
    """
    List tasks in a workspace. Optionally filter by status, project, or assignee.
    status values: todo | in_progress | done | cancelled
    Returns up to limit tasks (default 15, max 30).
    """
    async with AsyncSessionLocal() as db:
        q = (
            select(Task, User.name.label("assignee_name"), Project.name.label("project_name"))
            .outerjoin(User, User.id == Task.assignee_id)
            .outerjoin(Project, Project.id == Task.project_id)
            .where(Task.workspace_id == uuid.UUID(workspace_id))
        )
        if status:
            q = q.where(Task.status == TaskStatus(status))
        if project_id:
            q = q.where(Task.project_id == uuid.UUID(project_id))
        if assignee_id:
            uid = uuid.UUID(assignee_id)
            q = q.where(
                or_(
                    Task.assignee_id == uid,
                    Task.id.in_(
                        select(TaskAssignee.task_id).where(TaskAssignee.user_id == uid)
                    ),
                )
            )
        q = q.order_by(Task.created_at.asc()).limit(min(limit, 30))
        result = await db.execute(q)
        rows = result.all()
        assignee_map = await load_assignees_by_task(db, [r.Task.id for r in rows])
        tasks_out = [_enrich_task_row(row, assignee_map) for row in rows]
    await agent_broadcast(workspace_id, "lno_list_tasks", "done",
                          f"Found {len(tasks_out)} tasks" + (f" ({status})" if status else ""))
    return tasks_out


@mcp.tool()
async def lno_list_overdue_tasks(workspace_id: str, days_overdue: int = 1) -> list[dict]:
    """
    Return tasks overdue by at least `days_overdue` days. Excludes done and cancelled.
    """
    cutoff = date.today() - timedelta(days=days_overdue)
    async with AsyncSessionLocal() as db:
        q = (
            select(Task, User.name.label("assignee_name"))
            .outerjoin(User, User.id == Task.assignee_id)
            .where(
                and_(
                    Task.workspace_id == uuid.UUID(workspace_id),
                    Task.status.notin_([TaskStatus.done, TaskStatus.cancelled]),
                    Task.due_date <= cutoff,
                    Task.due_date.isnot(None),
                )
            )
            .order_by(Task.due_date.asc())
            .limit(30)
        )
        result = await db.execute(q)
        rows = result.all()
        assignee_map = await load_assignees_by_task(db, [r.Task.id for r in rows])
        overdue_out = [
            {
                **_enrich_task_row(row, assignee_map),
                "days_overdue": (date.today() - row.Task.due_date).days,
            }
            for row in rows
        ]
    await agent_broadcast(workspace_id, "lno_list_overdue_tasks", "done",
                          f"Found {len(overdue_out)} overdue tasks")
    return overdue_out


@mcp.tool()
async def lno_create_task(
    workspace_id: str,
    title: str,
    priority: str = "medium",
    assignee_id: Optional[str] = None,
    assignee_ids: Optional[list[str]] = None,
    project_id: Optional[str] = None,
    due_date: Optional[str] = None,
    description: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """
    Propose creating a new task. Creates a pending proposed_action for human approval.
    Returns: {"proposed": true, "action_id": "<uuid>", "message": "..."}
    """
    payload = {
        "workspace_id": workspace_id,
        "title": title,
        "priority": priority,
        "project_id": project_id,
        "due_date": due_date,
        "description": description,
    }
    if assignee_ids is not None:
        payload["assignee_ids"] = assignee_ids
    elif assignee_id is not None:
        payload["assignee_id"] = assignee_id

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            run_id=uuid.UUID(run_id) if run_id else None,
            action_type="create_task",
            payload=payload,
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        result = {
            "proposed": True,
            "action_id": str(action.id),
            "message": f"Task creation '{title}' queued for human approval (action {action.id}).",
        }
    await agent_broadcast(workspace_id, "lno_create_task", "done",
                          f"Proposed task: '{title}'")
    return result


@mcp.tool()
async def lno_update_task(
    workspace_id: str,
    task_id: str,
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assignee_id: Optional[str] = None,
    assignee_ids: Optional[list[str]] = None,
    due_date: Optional[str] = None,
    title: Optional[str] = None,
) -> dict:
    """
    Propose updating an existing task. Creates a pending proposed_action.
    Provide only fields to change.
    Returns: {"proposed": true, "action_id": "<uuid>", "message": "..."}
    """
    patch = {}
    if status is not None:
        patch["status"] = status
    if priority is not None:
        patch["priority"] = priority
    if assignee_ids is not None:
        patch["assignee_ids"] = assignee_ids
    elif assignee_id is not None:
        patch["assignee_id"] = assignee_id
    if due_date is not None:
        patch["due_date"] = due_date
    if title is not None:
        patch["title"] = title

    if not patch:
        return {"proposed": False, "message": "No fields to update provided."}

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            run_id=uuid.UUID(run_id) if run_id else None,
            action_type="update_task",
            payload={"workspace_id": workspace_id, "task_id": task_id, "patch": patch},
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        result = {
            "proposed": True,
            "action_id": str(action.id),
            "message": f"Task update on {task_id} queued for approval. Patch: {patch}",
        }
    await agent_broadcast(workspace_id, "lno_update_task", "done",
                          f"Proposed update on task {task_id[:8]}: {list(patch.keys())}")
    return result
