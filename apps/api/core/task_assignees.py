"""Helpers for task ↔ user many-to-many assignees."""
from __future__ import annotations

import uuid
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification, Task, TaskAssignee, WorkspaceMember


def normalize_assignee_ids(
    assignee_id: str | None = None,
    assignee_ids: list[str] | None = None,
) -> list[uuid.UUID]:
    """Merge legacy single assignee_id with assignee_ids (deduped, order preserved)."""
    out: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for raw in list(assignee_ids or []) + ([assignee_id] if assignee_id else []):
        if not raw:
            continue
        try:
            uid = uuid.UUID(str(raw))
        except ValueError:
            raise HTTPException(422, f"Invalid assignee id: {raw}")
        if uid not in seen:
            seen.add(uid)
            out.append(uid)
    return out


async def _assert_workspace_members(
    db: AsyncSession, workspace_id: uuid.UUID, user_ids: Iterable[uuid.UUID]
) -> None:
    ids = list(user_ids)
    if not ids:
        return
    result = await db.execute(
        select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id.in_(ids),
        )
    )
    found = {row[0] for row in result.all()}
    missing = [str(u) for u in ids if u not in found]
    if missing:
        raise HTTPException(422, f"Assignee(s) not in workspace: {', '.join(missing)}")


async def set_task_assignees(
    db: AsyncSession,
    task: Task,
    user_ids: list[uuid.UUID],
    *,
    actor_user_id: uuid.UUID | None = None,
    notify: bool = True,
) -> None:
    """Replace assignees for a task; sync legacy assignee_id to first assignee."""
    await _assert_workspace_members(db, task.workspace_id, user_ids)

    await db.execute(delete(TaskAssignee).where(TaskAssignee.task_id == task.id))
    for uid in user_ids:
        db.add(TaskAssignee(task_id=task.id, user_id=uid))

    task.assignee_id = user_ids[0] if user_ids else None

    if notify and actor_user_id:
        for uid in user_ids:
            if uid != actor_user_id:
                db.add(
                    Notification(
                        user_id=uid,
                        type="task_assigned",
                        entity_type="task",
                        entity_id=task.id,
                        message=f"You were assigned: {task.title}",
                    )
                )


async def load_assignees_by_task(
    db: AsyncSession, task_ids: list[uuid.UUID]
) -> dict[str, list[dict]]:
    if not task_ids:
        return {}
    from models import User

    result = await db.execute(
        select(TaskAssignee.task_id, TaskAssignee.user_id, User.name)
        .join(User, User.id == TaskAssignee.user_id)
        .where(TaskAssignee.task_id.in_(task_ids))
        .order_by(TaskAssignee.assigned_at.asc())
    )
    out: dict[str, list[dict]] = {}
    for task_id, user_id, name in result.all():
        key = str(task_id)
        out.setdefault(key, []).append({"id": str(user_id), "name": name})
    return out


def task_assignee_fields(assignees: list[dict]) -> dict:
    """API shape: assignee_ids, assignee_names, assignee_id (first, backward compat)."""
    return {
        "assignee_ids": [a["id"] for a in assignees],
        "assignee_names": [a["name"] for a in assignees],
        "assignee_id": assignees[0]["id"] if assignees else None,
    }
