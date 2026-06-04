from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from db.session import get_db
from models import User, Task, Project, TaskStatus, TaskPriority, WorkspaceMember, TaskAssignee
from core.task_assignees import (
    normalize_assignee_ids,
    set_task_assignees,
    load_assignees_by_task,
    task_assignee_fields,
)
from models.agent import ProposedAction
from core.auth import get_current_user
from core.config import settings
from agents.company_context import COMPANY_CONTEXT
from agents.memory_agent import MemoryAgent
from agents.memory_store import get_memories, upsert_memories
from pydantic import BaseModel
from core.model_router import chat_with_fallback, get_openrouter_client, models_for_profile
from core.chat_compression import compress_and_extract
from typing import Any
import json
import logging
import uuid
import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/ai", tags=["ai"])


def _successful_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [a for a in actions if (a.get("result") or {}).get("ok")]


# Write tool names that should be recorded in the ProposedAction audit log
_WRITE_TOOLS = {"create_task", "create_tasks", "update_task", "create_project", "update_project"}


async def _record_ai_action(
    db: AsyncSession,
    workspace_id: str,
    user_id: uuid.UUID,
    tool_name: str,
    args: dict,
    result: dict,
) -> None:
    """
    Record AI chat write operations as executed ProposedActions (audit trail).
    Makes AI chat writes visible in the Agents > Actions tab.
    Also broadcasts to the live WebSocket feed.
    """
    if tool_name not in _WRITE_TOOLS:
        return
    if not result.get("ok"):
        return
    try:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type=tool_name,
            payload=args,
            risk_level="low",
            status="executed",
            decided_by=user_id,
            decided_at=datetime.datetime.now(datetime.timezone.utc),
            execution_result=result,
        )
        db.add(action)
        await db.commit()

        # Broadcast to live feed (visible in Agents > Live Feed)
        try:
            from mcp_server.server import agent_broadcast
            summary = (
                args.get("title")
                or (f"{len(args.get('tasks', []))} tasks" if tool_name == "create_tasks" else None)
                or args.get("name")
                or tool_name
            )
            await agent_broadcast(
                workspace_id,
                f"ai:{tool_name}",
                "done",
                f"AI chat: {summary}",
            )
        except Exception:
            pass  # broadcast failure never blocks the response
    except Exception as e:
        logger.warning(f"[ai_action_record] failed for {tool_name}: {e}")


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []  # [{role: "user"|"assistant", content: str}]


class ExtractTasksRequest(BaseModel):
    message: str


AI_ACTION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_projects",
            "description": "List projects in the current workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_project",
            "description": "Create a new project in the current workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_project",
            "description": "Update an existing project by id",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks in the current workspace with optional filters",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "assignee_id": {"type": "string"},
                    "assignee_ids": {"type": "array", "items": {"type": "string"}},
                    "project_id": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create one task. assignee_id / assignee_ids are OPTIONAL. Use project_name (e.g. pmwani) instead of project_id when possible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "assignee_id": {"type": "string", "description": "Optional single assignee UUID"},
                    "assignee_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional multiple assignee UUIDs"},
                    "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "project_id": {"type": "string"},
                    "project_name": {"type": "string", "description": "Project name to link (preferred over project_id)"},
                    "parent_task_id": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_tasks",
            "description": "Create multiple tasks at once for a project. assignee_id / assignee_ids optional on each task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "project_name": {"type": "string"},
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "due_date": {"type": "string"},
                                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                                "assignee_id": {"type": "string"},
                                "assignee_ids": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["title"],
                        },
                    },
                },
                "required": ["tasks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task by id",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["todo", "in_progress", "done", "cancelled"]},
                    "assignee_id": {"type": "string"},
                    "assignee_ids": {"type": "array", "items": {"type": "string"}},
                    "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                    "project_id": {"type": "string"},
                    "parent_task_id": {"type": "string"},
                },
                "required": ["task_id"],
            },
        },
    },
]


def _safe_uuid(value: Any) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


def _parse_due_date(value: Any) -> datetime.date | None:
    if value is None or value == "":
        return None
    raw = str(value).strip()
    titled = raw.title()
    for candidate in (raw, titled):
        for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(candidate, fmt).date()
            except Exception:
                continue
    try:
        return datetime.date.fromisoformat(raw)
    except Exception:
        return None


_ASSIGNEE_PLACEHOLDERS = {
    "",
    "later",
    "tbd",
    "none",
    "null",
    "unassigned",
    "n/a",
    "na",
    "assign later",
    "assignee later",
}


def _sanitize_assignee_id(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in _ASSIGNEE_PLACEHOLDERS:
        return None
    return _safe_uuid(value)


def _task_out(task: Task, assignees: list[dict] | None = None) -> dict:
    base = {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "status": task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
        "priority": task.priority.value if isinstance(task.priority, TaskPriority) else str(task.priority),
        "due_date": str(task.due_date) if task.due_date else None,
        "project_id": str(task.project_id) if task.project_id else None,
        "parent_task_id": str(task.parent_task_id) if task.parent_task_id else None,
        "source_message_id": str(task.source_message_id) if task.source_message_id else None,
    }
    if assignees:
        base.update(task_assignee_fields(assignees))
    else:
        base["assignee_id"] = str(task.assignee_id) if task.assignee_id else None
        base["assignee_ids"] = []
        base["assignee_names"] = []
    return base


async def _task_out_db(db: AsyncSession, task: Task) -> dict:
    assignee_map = await load_assignees_by_task(db, [task.id])
    return _task_out(task, assignee_map.get(str(task.id), []))


def _project_out(project: Project) -> dict:
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status,
    }


async def _resolve_project(
    db: AsyncSession,
    workspace_uuid: uuid.UUID,
    project_id: Any = None,
    project_name: Any = None,
) -> tuple[Project | None, str | None]:
    if project_id:
        project_uuid = _safe_uuid(project_id)
        if project_uuid:
            result = await db.execute(
                select(Project).where(Project.id == project_uuid, Project.workspace_id == workspace_uuid)
            )
            project = result.scalar_one_or_none()
            if project:
                return project, None
        return None, "invalid project_id"

    if project_name:
        needle = str(project_name).strip().lower()
        if not needle:
            return None, "project_name is empty"
        result = await db.execute(select(Project).where(Project.workspace_id == workspace_uuid))
        projects = list(result.scalars().all())
        exact = [p for p in projects if p.name.lower() == needle]
        if len(exact) == 1:
            return exact[0], None
        partial = [p for p in projects if needle in p.name.lower()]
        if len(partial) == 1:
            return partial[0], None
        if len(partial) > 1:
            names = ", ".join(p.name for p in partial[:5])
            return None, f"multiple projects match '{project_name}': {names}"
        return None, f"project '{project_name}' not found"

    return None, None


async def _build_workspace_snapshot(db: AsyncSession, workspace_id: str) -> str:
    workspace_uuid = uuid.UUID(workspace_id)
    projects_result = await db.execute(
        select(Project).where(Project.workspace_id == workspace_uuid).order_by(Project.created_at.asc())
    )
    projects = [_project_out(p) for p in projects_result.scalars().all()]

    tasks_result = await db.execute(
        select(Task).where(Task.workspace_id == workspace_uuid).order_by(Task.created_at.desc()).limit(25)
    )
    tasks = [_task_out(t) for t in tasks_result.scalars().all()]

    members_result = await db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_uuid)
    )
    members = [
        {"id": str(user.id), "name": user.name, "email": user.email}
        for _, user in members_result.all()
    ]

    return (
        "## Workspace Snapshot (live)\n"
        f"Projects ({len(projects)}): {json.dumps(projects)}\n"
        f"Recent tasks ({len(tasks)}): {json.dumps(tasks)}\n"
        f"Team members ({len(members)}): {json.dumps(members)}\n"
        "Use project_name when creating tasks. assignee_id is optional."
    )


_HISTORY_COMPRESS_THRESHOLD = 30   # messages; trigger compaction
_HISTORY_KEEP_RECENT = 10          # messages to keep verbatim after compression


async def _maybe_compress_history(
    history: list[dict],
    workspace_id: str,
    db: AsyncSession,
) -> tuple[list[dict], bool]:
    """
    If history exceeds threshold, summarise the oldest chunk and return a
    compressed history list. Returns (history, did_compress).
    On failure returns (original_history, False).
    """
    if len(history) < _HISTORY_COMPRESS_THRESHOLD:
        return history, False

    old = history[:-_HISTORY_KEEP_RECENT]
    recent = history[-_HISTORY_KEEP_RECENT:]

    # Pair messages by role — walk old, match each user turn with the next assistant turn
    exchanges: list[dict] = []
    pending_user: str | None = None
    for msg in old:
        role = msg.get("role", "")
        content = msg.get("content", "") or ""
        if role == "user":
            if pending_user is not None:
                exchanges.append({"user": pending_user, "hermes": ""})
            pending_user = content
        elif role == "assistant" and pending_user is not None:
            exchanges.append({"user": pending_user, "hermes": content})
            pending_user = None
    if pending_user is not None:
        exchanges.append({"user": pending_user, "hermes": ""})

    try:
        summary = await compress_and_extract(exchanges, None, workspace_id, db)
    except Exception:
        return history, False

    summary_msg = {"role": "system", "content": f"[CONVERSATION SUMMARY]\n{summary}"}
    return [summary_msg, *recent], True


def _format_action_summary(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return ""
    lines: list[str] = []
    for action in actions:
        result = action.get("result") or {}
        tool = action.get("tool", "action")
        if not result.get("ok"):
            lines.append(f"- {tool} failed: {result.get('error', 'unknown error')}")
            continue
        if tool == "create_project" and result.get("project"):
            p = result["project"]
            lines.append(f"- Created project **{p['name']}** (`{p['id']}`)")
        elif tool == "create_task" and result.get("task"):
            t = result["task"]
            due = f", due {t['due_date']}" if t.get("due_date") else ""
            lines.append(f"- Created task **{t['title']}**{due}")
        elif tool == "create_tasks" and result.get("tasks"):
            for t in result["tasks"]:
                due = f", due {t['due_date']}" if t.get("due_date") else ""
                lines.append(f"- Created task **{t['title']}**{due}")
            if result.get("errors"):
                for err in result["errors"]:
                    lines.append(f"- Skipped task: {err}")
        elif tool == "update_task" and result.get("task"):
            t = result["task"]
            lines.append(f"- Updated task **{t['title']}** (status: {t['status']})")
        elif tool == "update_project" and result.get("project"):
            p = result["project"]
            lines.append(f"- Updated project **{p['name']}**")
        elif tool in ("list_tasks", "list_projects"):
            count = result.get("count", 0)
            lines.append(f"- Listed {count} {tool.replace('list_', '')}")
        else:
            lines.append(f"- {tool} completed")

    if not lines:
        ok_count = len(_successful_actions(actions))
        if ok_count:
            return f"Completed {ok_count} action(s) in your workspace."
        return ""
    return "Done:\n" + "\n".join(lines)


async def _create_task_record(
    db: AsyncSession,
    workspace_uuid: uuid.UUID,
    current_user: User,
    *,
    title: str,
    description: Any = None,
    assignee_id: Any = None,
    assignee_ids: Any = None,
    due_date_raw: Any = None,
    priority_raw: Any = "medium",
    project_id: Any = None,
    project_name: Any = None,
    parent_task_id: Any = None,
) -> dict:
    title = (title or "").strip()
    if not title:
        return {"ok": False, "error": "title is required"}

    try:
        priority = TaskPriority(str(priority_raw or "medium"))
    except Exception:
        return {"ok": False, "error": "invalid priority"}

    single_raw: str | None = None
    if assignee_id is not None and str(assignee_id).strip().lower() not in _ASSIGNEE_PLACEHOLDERS:
        assignee_uuid = _sanitize_assignee_id(assignee_id)
        if assignee_uuid is None:
            return {"ok": False, "error": "invalid assignee_id"}
        single_raw = str(assignee_uuid)
    try:
        assignee_uuids = normalize_assignee_ids(single_raw, assignee_ids)
    except HTTPException as e:
        return {"ok": False, "error": e.detail}

    project, project_err = await _resolve_project(db, workspace_uuid, project_id, project_name)
    if project_err:
        return {"ok": False, "error": project_err}

    parent_task_uuid = _safe_uuid(parent_task_id)
    if parent_task_id is not None and parent_task_uuid is None:
        return {"ok": False, "error": "invalid parent_task_id"}

    due_date = _parse_due_date(due_date_raw)
    if due_date_raw is not None and str(due_date_raw).strip() and due_date is None:
        return {"ok": False, "error": "invalid due_date (use YYYY-MM-DD)"}

    task = Task(
        workspace_id=workspace_uuid,
        title=title,
        description=description,
        assignee_id=assignee_uuids[0] if assignee_uuids else None,
        due_date=due_date,
        priority=priority,
        project_id=project.id if project else None,
        parent_task_id=parent_task_uuid,
        created_by=current_user.id,
        tags=[],
    )
    db.add(task)
    await db.flush()
    if assignee_uuids:
        await set_task_assignees(
            db, task, assignee_uuids, actor_user_id=current_user.id, notify=True
        )
    await db.commit()
    await db.refresh(task)
    return {"ok": True, "task": await _task_out_db(db, task)}


async def _run_ai_tool(
    tool_name: str,
    args: dict,
    workspace_id: str,
    current_user: User,
    db: AsyncSession,
) -> dict:
    workspace_uuid = uuid.UUID(workspace_id)

    if tool_name == "list_projects":
        query = select(Project).where(Project.workspace_id == workspace_uuid).order_by(Project.created_at.asc())
        status = args.get("status")
        if status:
            query = query.where(Project.status == str(status))
        result = await db.execute(query)
        projects = [_project_out(project) for project in result.scalars().all()]
        return {"ok": True, "count": len(projects), "projects": projects[:30]}

    if tool_name == "create_project":
        name = (args.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "name is required"}
        project = Project(
            workspace_id=workspace_uuid,
            name=name,
            description=args.get("description"),
            status=args.get("status") or "active",
            created_by=current_user.id,
        )
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return {"ok": True, "project": _project_out(project)}

    if tool_name == "update_project":
        project_uuid = _safe_uuid(args.get("project_id"))
        if not project_uuid:
            return {"ok": False, "error": "valid project_id is required"}
        result = await db.execute(
            select(Project).where(Project.id == project_uuid, Project.workspace_id == workspace_uuid)
        )
        project = result.scalar_one_or_none()
        if not project:
            return {"ok": False, "error": "project not found"}
        if args.get("name") is not None:
            project.name = str(args.get("name"))
        if args.get("description") is not None:
            project.description = args.get("description")
        if args.get("status") is not None:
            project.status = str(args.get("status"))
        await db.commit()
        await db.refresh(project)
        return {"ok": True, "project": _project_out(project)}

    if tool_name == "list_tasks":
        query = select(Task).where(Task.workspace_id == workspace_uuid).order_by(Task.created_at.asc())
        status = args.get("status")
        if status:
            try:
                query = query.where(Task.status == TaskStatus(str(status)))
            except Exception:
                return {"ok": False, "error": "invalid status"}
        assignee_uuid = _safe_uuid(args.get("assignee_id"))
        if args.get("assignee_id") is not None and assignee_uuid is None:
            return {"ok": False, "error": "invalid assignee_id"}
        if assignee_uuid:
            query = query.where(
                or_(
                    Task.assignee_id == assignee_uuid,
                    Task.id.in_(
                        select(TaskAssignee.task_id).where(
                            TaskAssignee.user_id == assignee_uuid
                        )
                    ),
                )
            )
        project_uuid = _safe_uuid(args.get("project_id"))
        if args.get("project_id") is not None and project_uuid is None:
            return {"ok": False, "error": "invalid project_id"}
        if project_uuid:
            query = query.where(Task.project_id == project_uuid)
        result = await db.execute(query)
        task_rows = result.scalars().all()
        assignee_map = await load_assignees_by_task(db, [t.id for t in task_rows])
        tasks = [
            _task_out(t, assignee_map.get(str(t.id), [])) for t in task_rows
        ]
        return {"ok": True, "count": len(tasks), "tasks": tasks[:40]}

    if tool_name == "create_task":
        return await _create_task_record(
            db,
            workspace_uuid,
            current_user,
            title=args.get("title"),
            description=args.get("description"),
            assignee_id=args.get("assignee_id"),
            assignee_ids=args.get("assignee_ids"),
            due_date_raw=args.get("due_date"),
            priority_raw=args.get("priority"),
            project_id=args.get("project_id"),
            project_name=args.get("project_name"),
            parent_task_id=args.get("parent_task_id"),
        )

    if tool_name == "create_tasks":
        items = args.get("tasks") or []
        if not isinstance(items, list) or not items:
            return {"ok": False, "error": "tasks array is required"}
        created: list[dict] = []
        errors: list[str] = []
        for idx, item in enumerate(items[:20]):
            if not isinstance(item, dict):
                errors.append(f"item {idx + 1}: invalid task object")
                continue
            result = await _create_task_record(
                db,
                workspace_uuid,
                current_user,
                title=item.get("title"),
                description=item.get("description"),
                assignee_id=item.get("assignee_id"),
                assignee_ids=item.get("assignee_ids"),
                due_date_raw=item.get("due_date"),
                priority_raw=item.get("priority"),
                project_id=args.get("project_id"),
                project_name=args.get("project_name"),
                parent_task_id=item.get("parent_task_id"),
            )
            if result.get("ok") and result.get("task"):
                created.append(result["task"])
            else:
                errors.append(f"{item.get('title', f'item {idx + 1}')}: {result.get('error', 'failed')}")
        return {
            "ok": bool(created),
            "count": len(created),
            "tasks": created,
            "errors": errors,
        }

    if tool_name == "update_task":
        task_uuid = _safe_uuid(args.get("task_id"))
        if not task_uuid:
            return {"ok": False, "error": "valid task_id is required"}
        result = await db.execute(select(Task).where(Task.id == task_uuid, Task.workspace_id == workspace_uuid))
        task = result.scalar_one_or_none()
        if not task:
            return {"ok": False, "error": "task not found"}

        if args.get("title") is not None:
            task.title = str(args.get("title"))
        if args.get("description") is not None:
            task.description = args.get("description")
        if args.get("status") is not None:
            try:
                task.status = TaskStatus(str(args.get("status")))
            except Exception:
                return {"ok": False, "error": "invalid status"}
        if args.get("priority") is not None:
            try:
                task.priority = TaskPriority(str(args.get("priority")))
            except Exception:
                return {"ok": False, "error": "invalid priority"}
        if args.get("assignee_ids") is not None or args.get("assignee_id") is not None:
            try:
                if args.get("assignee_ids") is not None:
                    assignee_uuids = normalize_assignee_ids(None, args.get("assignee_ids"))
                else:
                    assignee_uuid = _safe_uuid(args.get("assignee_id"))
                    if assignee_uuid is None and args.get("assignee_id"):
                        return {"ok": False, "error": "invalid assignee_id"}
                    assignee_uuids = normalize_assignee_ids(
                        str(assignee_uuid) if assignee_uuid else None, None
                    )
            except HTTPException as e:
                return {"ok": False, "error": e.detail}
            await set_task_assignees(
                db, task, assignee_uuids, actor_user_id=current_user.id, notify=True
            )
        if args.get("project_id") is not None or args.get("project_name") is not None:
            project, project_err = await _resolve_project(
                db, workspace_uuid, args.get("project_id"), args.get("project_name")
            )
            if project_err:
                return {"ok": False, "error": project_err}
            task.project_id = project.id if project else None
        if args.get("parent_task_id") is not None:
            parent_task_uuid = _safe_uuid(args.get("parent_task_id"))
            if parent_task_uuid is None:
                return {"ok": False, "error": "invalid parent_task_id"}
            task.parent_task_id = parent_task_uuid
        if args.get("due_date") is not None:
            due_date = _parse_due_date(args.get("due_date"))
            if due_date is None:
                return {"ok": False, "error": "invalid due_date (use YYYY-MM-DD)"}
            task.due_date = due_date

        await db.commit()
        await db.refresh(task)
        return {"ok": True, "task": await _task_out_db(db, task)}

    return {"ok": False, "error": f"unknown tool: {tool_name}"}


async def _extract_and_store_memories(
    workspace_id: str,
    user_message: str,
    assistant_reply: str,
    existing_keys: list[str],
):
    """Background task: extract memories from this conversation turn and store them."""
    try:
        from db.session import AsyncSessionLocal
        conversation = f"User: {user_message}\nAssistant: {assistant_reply}"
        agent = MemoryAgent()
        new_memories = agent.extract(conversation, existing_keys)
        if new_memories:
            async with AsyncSessionLocal() as db:
                count = await upsert_memories(db, workspace_id, new_memories, source="ai")
                if count:
                    logger.info(f"[memory] stored {count} memories for workspace {workspace_id}")
    except Exception as e:
        logger.warning(f"[memory] background extraction failed: {e}")


@router.post("/chat")
async def ai_chat(
    workspace_id: str,
    body: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Chat with the AI workspace assistant via OpenRouter, with memory injection."""
    if not settings.openrouter_api_key:
        raise HTTPException(503, "AI not configured — set OPENROUTER_API_KEY in .env")

    # Fetch relevant memories
    memories = await get_memories(db, workspace_id, limit=20)
    memory_agent = MemoryAgent()
    memory_section = memory_agent.format_for_context(memories)
    existing_keys = [m["key"] for m in memories]

    workspace_snapshot = await _build_workspace_snapshot(db, workspace_id)

    history, _did_compress = await _maybe_compress_history(body.history, workspace_id, db)

    system = (
        "You are the AI assistant embedded in LNO OS — LNO Technology's internal operating system.\n"
        "You help the founding team manage tasks, communications, and company knowledge.\n"
        "Be concise, direct, and founder-mode.\n\n"
        "## Action rules (critical)\n"
        "- When the user asks to create/update tasks or projects, USE TOOLS immediately — do not only describe steps.\n"
        "- assignee_id is OPTIONAL. Never ask for assignee IDs unless user explicitly wants assignment now.\n"
        "- Prefer project_name (example: pmwani) over project_id when linking tasks.\n"
        "- For multiple tasks, call create_tasks in one shot.\n"
        "- Parse due dates to YYYY-MM-DD (example: 5 July 2026 -> 2026-07-05).\n"
        "- After tools run, always send a short confirmation listing what was created/updated.\n"
        "- Before destructive changes, ask for explicit confirmation.\n\n"
        f"## Company Context\n{COMPANY_CONTEXT}\n\n"
        f"{workspace_snapshot}"
    )

    if memory_section:
        system += f"\n\n{memory_section}"

    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": body.message},
    ]

    executed_actions: list[dict[str, Any]] = []
    reply = ""
    model_used = models_for_profile("agent_tools")[0]
    client = get_openrouter_client()

    max_tool_rounds = 6
    for round_idx in range(max_tool_rounds):
        use_tools = round_idx < max_tool_rounds - 1

        try:
            response, model_used = chat_with_fallback(
                profile="agent_tools" if use_tools else "agent_chat",
                messages=messages,
                max_tokens=1024,
                tools=AI_ACTION_TOOLS if use_tools else None,
                tool_choice="auto" if use_tools else None,
                client=client,
            )
        except Exception as e:
            logger.warning(f"[ai/chat] model call failed: {e}")
            break

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            text = (assistant_message.content or "").strip()
            if text:
                reply = text
            break

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except Exception:
                args = {}
            try:
                result = await _run_ai_tool(tool_name, args, workspace_id, current_user, db)
            except Exception as e:
                logger.warning(f"[ai/chat] tool {tool_name} failed: {e}")
                result = {"ok": False, "error": str(e)}
            executed_actions.append({"tool": tool_name, "args": args, "result": result})
            # Record write operations as executed ProposedActions (audit trail + live feed)
            await _record_ai_action(db, workspace_id, current_user.id, tool_name, args, result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

        # Tools ran successfully but free-tier models often skip the final text response.
        # Build a user-facing confirmation immediately so UI never shows a false error.
        if _successful_actions(executed_actions):
            summary = _format_action_summary(executed_actions)
            if summary:
                reply = summary

    if not reply.strip() and _successful_actions(executed_actions):
        reply = _format_action_summary(executed_actions) or (
            f"Completed {len(_successful_actions(executed_actions))} action(s) in your workspace."
        )

    if not reply.strip() and executed_actions:
        try:
            finalize, model_used = chat_with_fallback(
                profile="agent_chat",
                messages=[
                    *messages,
                    {
                        "role": "user",
                        "content": "Summarize what you accomplished for the user in 2-4 concise sentences.",
                    },
                ],
                max_tokens=512,
                client=client,
            )
            reply = (finalize.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"[ai/chat] finalize failed: {e}")

    if not reply.strip() and _successful_actions(executed_actions):
        reply = _format_action_summary(executed_actions)

    if not reply.strip():
        failed = [a for a in executed_actions if not (a.get("result") or {}).get("ok")]
        if failed:
            err = failed[-1]["result"].get("error", "unknown error")
            reply = f"I couldn't finish that action: {err}"
        elif executed_actions:
            reply = "Actions were attempted but no confirmation text was returned. Check Tasks/Projects — changes may still have been applied."
        else:
            reply = "I couldn't generate a response. Please retry once."

    # Fire-and-forget: extract memories from this conversation
    background_tasks.add_task(
        _extract_and_store_memories,
        workspace_id,
        body.message,
        reply,
        existing_keys,
    )

    out: dict = {"reply": reply, "actions": executed_actions, "model_used": model_used}
    if _did_compress:
        out["compressed_history"] = history
    return out


@router.post("/extract-tasks")
async def extract_tasks(
    workspace_id: str,
    body: ExtractTasksRequest,
    current_user: User = Depends(get_current_user),
):
    """Extract actionable tasks from a message using AI via OpenRouter."""
    if not settings.openrouter_api_key:
        return {"tasks": []}  # Graceful degradation — no key, no tasks

    prompt = (
        "Extract actionable tasks from this message. Return ONLY a JSON array of task objects. "
        'Each task has: title (string, max 80 chars), description (string, optional), priority ("low"|"medium"|"high"|"urgent"). '
        "If there are no clear tasks, return an empty array [].\n\n"
        f"Message: {body.message}\n\n"
        "Respond with ONLY the JSON array, no explanation."
    )

    try:
        response, _ = chat_with_fallback(
            profile="extract_tasks",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = (response.choices[0].message.content or "").strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            tasks = json.loads(text[start:end])
            return {"tasks": tasks[:5]}
    except Exception:
        pass

    return {"tasks": []}
