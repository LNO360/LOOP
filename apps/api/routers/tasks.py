from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, delete
from db.session import get_db
from models import Task, TaskStatus, TaskPriority, TaskAssignee, User, TaskComment
from core.auth import get_current_user
from core.task_assignees import (
    normalize_assignee_ids,
    set_task_assignees,
    load_assignees_by_task,
    task_assignee_fields,
)
from pydantic import BaseModel
from typing import Optional
import uuid, datetime

router = APIRouter(prefix="/workspaces/{workspace_id}/tasks", tags=["tasks"])

class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_ids: Optional[list[str]] = None
    due_date: Optional[str] = None
    priority: str = "medium"
    project_id: Optional[str] = None
    source_message_id: Optional[str] = None
    tags: Optional[list[str]] = None
    parent_task_id: Optional[str] = None

class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_ids: Optional[list[str]] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[list[str]] = None
    parent_task_id: Optional[str] = None
    project_id: Optional[str] = None

@router.get("")
async def list_tasks(workspace_id: str, status: Optional[str] = None, assignee_id: Optional[str] = None, parent_task_id: Optional[str] = None, project_id: Optional[str] = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = select(Task).where(Task.workspace_id == uuid.UUID(workspace_id))
    if status:
        q = q.where(Task.status == TaskStatus(status))
    if assignee_id:
        uid = uuid.UUID(assignee_id)
        q = q.where(
            or_(
                Task.assignee_id == uid,
                Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == uid)),
            )
        )
    if parent_task_id == "none":
        q = q.where(Task.parent_task_id.is_(None))
    elif parent_task_id:
        q = q.where(Task.parent_task_id == uuid.UUID(parent_task_id))
    if project_id == "none":
        q = q.where(Task.project_id.is_(None))
    elif project_id:
        q = q.where(Task.project_id == uuid.UUID(project_id))
    q = q.order_by(Task.created_at.asc())
    result = await db.execute(q)
    tasks = list(result.scalars().all())
    assignee_map = await load_assignees_by_task(db, [t.id for t in tasks])
    return [_task_out(t, assignee_map.get(str(t.id), [])) for t in tasks]

@router.post("")
async def create_task(workspace_id: str, body: CreateTaskRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    assignee_uuids = normalize_assignee_ids(body.assignee_id, body.assignee_ids)
    task = Task(
        workspace_id=uuid.UUID(workspace_id),
        title=body.title,
        description=body.description,
        assignee_id=assignee_uuids[0] if assignee_uuids else None,
        due_date=datetime.date.fromisoformat(body.due_date) if body.due_date else None,
        priority=TaskPriority(body.priority),
        project_id=uuid.UUID(body.project_id) if body.project_id else None,
        source_message_id=uuid.UUID(body.source_message_id) if body.source_message_id else None,
        created_by=current_user.id,
        tags=body.tags or [],
        parent_task_id=uuid.UUID(body.parent_task_id) if body.parent_task_id else None,
    )
    db.add(task)
    await db.flush()
    if assignee_uuids:
        await set_task_assignees(
            db, task, assignee_uuids, actor_user_id=current_user.id, notify=True
        )
    await db.commit()
    await db.refresh(task)
    assignees = await load_assignees_by_task(db, [task.id])
    return _task_out(task, assignees.get(str(task.id), []))

@router.patch("/{task_id}")
async def update_task(workspace_id: str, task_id: str, body: UpdateTaskRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Task).where(Task.id == uuid.UUID(task_id)))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.status is not None:
        task.status = TaskStatus(body.status)
    if body.due_date is not None:
        task.due_date = datetime.date.fromisoformat(body.due_date)
    if body.priority is not None:
        task.priority = TaskPriority(body.priority)
    if body.tags is not None:
        task.tags = body.tags
    if body.parent_task_id is not None:
        task.parent_task_id = uuid.UUID(body.parent_task_id) if body.parent_task_id else None
    if body.project_id is not None:
        task.project_id = uuid.UUID(body.project_id) if body.project_id else None

    if body.assignee_ids is not None or body.assignee_id is not None:
        if body.assignee_ids is not None:
            assignee_uuids = normalize_assignee_ids(None, body.assignee_ids)
        else:
            assignee_uuids = normalize_assignee_ids(body.assignee_id, None)
        await set_task_assignees(
            db, task, assignee_uuids, actor_user_id=current_user.id, notify=True
        )

    await db.commit()
    await db.refresh(task)
    assignees = await load_assignees_by_task(db, [task.id])
    return _task_out(task, assignees.get(str(task.id), []))

async def _delete_task_tree(db: AsyncSession, task: Task) -> None:
    """Delete subtasks, comments, then the task (FK-safe order)."""
    subtasks = (
        await db.execute(select(Task).where(Task.parent_task_id == task.id))
    ).scalars().all()
    for child in subtasks:
        await _delete_task_tree(db, child)
    await db.execute(delete(TaskComment).where(TaskComment.task_id == task.id))
    await db.delete(task)


@router.delete("/{task_id}")
async def delete_task(
    workspace_id: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ws_id = uuid.UUID(workspace_id)
    result = await db.execute(
        select(Task).where(Task.id == uuid.UUID(task_id), Task.workspace_id == ws_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    await _delete_task_tree(db, task)
    await db.commit()
    return {"ok": True}

@router.get("/{task_id}/subtasks")
async def list_subtasks(workspace_id: str, task_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Task).where(Task.parent_task_id == uuid.UUID(task_id)).order_by(Task.created_at.asc()))
    tasks = list(result.scalars().all())
    assignee_map = await load_assignees_by_task(db, [t.id for t in tasks])
    return [_task_out(t, assignee_map.get(str(t.id), [])) for t in tasks]

def _task_out(t: Task, assignees: list[dict]) -> dict:
    base = {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "due_date": str(t.due_date) if t.due_date else None,
        "project_id": str(t.project_id) if t.project_id else None,
        "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
        "source_message_id": str(t.source_message_id) if t.source_message_id else None,
        "created_at": t.created_at.isoformat(),
        "tags": t.tags or [],
    }
    if assignees:
        base.update(task_assignee_fields(assignees))
    else:
        base.update(
            {
                "assignee_ids": [],
                "assignee_names": [],
                "assignee_id": str(t.assignee_id) if t.assignee_id else None,
            }
        )
    return base
