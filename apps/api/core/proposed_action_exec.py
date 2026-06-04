"""Execute or reject proposed actions (shared by REST API, MCP, Telegram flow)."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

import httpx as _httpx
from core.config import settings as _settings
from core.google_actions import (
    execute_gcal_create_event,
    execute_gcal_create_event_with_meet,
    execute_gcal_update_event,
    execute_gcal_delete_event,
    execute_gmail_send,
    execute_gmail_add_label,
    execute_gmail_archive,
    execute_gsheets_append_row,
    execute_gsheets_update_cells,
    execute_gdrive_upload_file,
)
from core.github_actions import execute_github_create_issue, execute_github_add_issue_comment
from models import Message, Project, Task, TaskPriority, TaskStatus, WorkspaceMember
from models.agent import ProposedAction


async def execute_proposed_action(
    action: ProposedAction,
    db: AsyncSession,
    *,
    workspace_id: str,
    actor_user_id: Optional[uuid.UUID],
) -> dict:
    """Run an approved proposed action. Raises HTTPException on failure."""
    if action.status != "pending":
        raise HTTPException(400, f"Action is already {action.status}")

    execution_result: dict = {}

    if action.action_type == "create_task":
        from core.task_assignees import normalize_assignee_ids, set_task_assignees

        p = action.payload
        assignee_uuids = normalize_assignee_ids(
            p.get("assignee_id"), p.get("assignee_ids")
        )
        task = Task(
            workspace_id=uuid.UUID(p["workspace_id"]),
            title=p["title"],
            description=p.get("description"),
            priority=TaskPriority(p.get("priority", "medium")),
            assignee_id=assignee_uuids[0] if assignee_uuids else None,
            project_id=uuid.UUID(p["project_id"]) if p.get("project_id") else None,
            created_by=actor_user_id,
            status=TaskStatus.todo,
        )
        db.add(task)
        await db.flush()
        if assignee_uuids:
            await set_task_assignees(
                db, task, assignee_uuids, actor_user_id=actor_user_id, notify=False
            )
        execution_result = {"created_task_id": str(task.id), "title": task.title}

    elif action.action_type == "update_task":
        p = action.payload
        task_result = await db.execute(select(Task).where(Task.id == uuid.UUID(p["task_id"])))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(404, f"Task {p['task_id']} not found")
        patch = p.get("patch", {})
        if "status" in patch:
            task.status = TaskStatus(patch["status"])
        if "priority" in patch:
            task.priority = TaskPriority(patch["priority"])
        if "assignee_ids" in patch or "assignee_id" in patch:
            from core.task_assignees import normalize_assignee_ids, set_task_assignees

            if "assignee_ids" in patch:
                assignee_uuids = normalize_assignee_ids(None, patch.get("assignee_ids"))
            else:
                assignee_uuids = normalize_assignee_ids(patch.get("assignee_id"), None)
            await set_task_assignees(
                db, task, assignee_uuids, actor_user_id=actor_user_id, notify=False
            )
        if "due_date" in patch:
            from datetime import date
            task.due_date = date.fromisoformat(patch["due_date"]) if patch["due_date"] else None
        if "title" in patch:
            task.title = patch["title"]
        execution_result = {"updated_task_id": str(task.id)}

    elif action.action_type == "send_channel_message":
        p = action.payload
        member_result = await db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == uuid.UUID(p["workspace_id"]))
            .limit(1)
        )
        member = member_result.scalar_one_or_none()
        author_id = member.user_id if member else actor_user_id
        msg = Message(
            channel_id=uuid.UUID(p["channel_id"]),
            author_id=author_id,
            content=p["content"],
        )
        db.add(msg)
        await db.flush()
        execution_result = {"sent_message_id": str(msg.id)}

    elif action.action_type == "create_project":
        p = action.payload
        project = Project(
            workspace_id=uuid.UUID(p["workspace_id"]),
            name=p["name"],
            description=p.get("description"),
            status=p.get("status", "active"),
            created_by=actor_user_id,  # projects.created_by is NOT NULL
        )
        db.add(project)
        await db.flush()
        execution_result = {"created_project_id": str(project.id), "name": project.name}

    elif action.action_type == "update_project":
        p = action.payload
        proj_result = await db.execute(
            select(Project).where(Project.id == uuid.UUID(p["project_id"]))
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            raise HTTPException(404, f"Project {p['project_id']} not found")
        patch = p.get("patch", {})
        if "status" in patch:
            project.status = patch["status"]
        if "name" in patch:
            project.name = patch["name"]
        if "description" in patch:
            project.description = patch["description"]
        execution_result = {"updated_project_id": str(project.id)}

    elif action.action_type == "delete_task":
        p = action.payload
        task_result = await db.execute(select(Task).where(Task.id == uuid.UUID(p["task_id"])))
        task = task_result.scalar_one_or_none()
        if not task:
            raise HTTPException(404, f"Task {p['task_id']} not found")
        await db.delete(task)
        execution_result = {"deleted_task_id": p["task_id"], "title": p.get("title")}

    elif action.action_type == "delete_message":
        p = action.payload
        msg_result = await db.execute(
            select(Message).where(Message.id == uuid.UUID(p["message_id"]))
        )
        msg = msg_result.scalar_one_or_none()
        if not msg:
            raise HTTPException(404, f"Message {p['message_id']} not found")
        msg.deleted_at = datetime.now(timezone.utc)
        execution_result = {"deleted_message_id": p["message_id"]}

    elif action.action_type == "delete_project":
        p = action.payload
        ws_uuid = uuid.UUID(p["workspace_id"])
        project_uuid = uuid.UUID(p["project_id"])
        proj_result = await db.execute(
            select(Project).where(Project.id == project_uuid, Project.workspace_id == ws_uuid)
        )
        project = proj_result.scalar_one_or_none()
        if not project:
            raise HTTPException(404, f"Project {p['project_id']} not found")
        if p.get("confirm_name", "").strip() != project.name:
            raise HTTPException(400, "confirm_name does not match project name")

        count_result = await db.execute(
            select(func.count()).select_from(Task).where(
                Task.workspace_id == ws_uuid,
                Task.project_id == project_uuid,
            )
        )
        task_count = int(count_result.scalar() or 0)
        if task_count > 0 and not p.get("acknowledge_tasks"):
            raise HTTPException(
                409,
                f"Project has {task_count} linked task(s); acknowledge_tasks required",
            )
        unlinked = 0
        if task_count > 0:
            unlink_result = await db.execute(
                update(Task)
                .where(Task.workspace_id == ws_uuid, Task.project_id == project_uuid)
                .values(project_id=None)
            )
            unlinked = unlink_result.rowcount or task_count
        await db.delete(project)
        execution_result = {"deleted_project_id": str(project_uuid), "unlinked_tasks": unlinked}

    elif action.action_type == "delete_skill":
        from pathlib import Path
        p = action.payload
        skill_path = p.get("skill_path", "")
        if not skill_path.startswith("user/"):
            raise HTTPException(400, "Cannot delete built-in skills")
        slug = skill_path.removeprefix("user/")
        user_skills = Path(__file__).resolve().parent.parent / "user-agent-skills"
        path = user_skills / f"{slug}.md"
        if path.exists():
            path.unlink()
        execution_result = {"deleted": skill_path}

    elif action.action_type == "gmail_send":
        execution_result = await execute_gmail_send(db, workspace_id, action.payload)

    elif action.action_type == "gmail_add_label":
        execution_result = await execute_gmail_add_label(db, workspace_id, action.payload)

    elif action.action_type == "gmail_archive":
        execution_result = await execute_gmail_archive(db, workspace_id, action.payload)

    elif action.action_type == "gcal_create_event":
        execution_result = await execute_gcal_create_event(db, workspace_id, action.payload)

    elif action.action_type == "gcal_create_event_with_meet":
        execution_result = await execute_gcal_create_event_with_meet(db, workspace_id, action.payload)

    elif action.action_type == "gcal_update_event":
        execution_result = await execute_gcal_update_event(db, workspace_id, action.payload)

    elif action.action_type == "gcal_delete_event":
        execution_result = await execute_gcal_delete_event(db, workspace_id, action.payload)

    elif action.action_type == "gsheets_append_row":
        execution_result = await execute_gsheets_append_row(db, workspace_id, action.payload)

    elif action.action_type == "gsheets_update_cells":
        execution_result = await execute_gsheets_update_cells(db, workspace_id, action.payload)

    elif action.action_type == "gdrive_upload_file":
        execution_result = await execute_gdrive_upload_file(db, workspace_id, action.payload)

    elif action.action_type == "github_create_issue":
        execution_result = await execute_github_create_issue(db, workspace_id, action.payload)

    elif action.action_type == "github_add_issue_comment":
        execution_result = await execute_github_add_issue_comment(db, workspace_id, action.payload)

    elif action.action_type == "finance_create_transaction":
        p = action.payload
        import uuid as _uuid
        from datetime import date as _date
        import services.finance_service as _fs
        execution_result = await _fs.create_transaction(
            db,
            _uuid.UUID(workspace_id),
            account_id=_uuid.UUID(p["account_id"]),
            direction=p["direction"],
            amount_cents=p["amount_cents"],
            occurred_on=_date.fromisoformat(p["occurred_on"]),
            description=p["description"],
            currency=p.get("currency", "INR"),
            category_id=_uuid.UUID(p["category_id"]) if p.get("category_id") else None,
            reference=p.get("reference"),
            source="agent",
            created_by=actor_user_id,
        )

    elif action.action_type == "finance_update_transaction":
        p = action.payload
        import uuid as _uuid
        from datetime import date as _date
        import services.finance_service as _fs
        patch = p.get("patch", {})
        kwargs = {}
        for k, v in patch.items():
            if k == "occurred_on":
                kwargs[k] = _date.fromisoformat(v)
            elif k == "category_id":
                kwargs[k] = _uuid.UUID(v) if v else None
            else:
                kwargs[k] = v
        execution_result = await _fs.update_transaction(
            db, _uuid.UUID(workspace_id), _uuid.UUID(p["transaction_id"]), **kwargs
        )

    elif action.action_type == "finance_delete_transaction":
        p = action.payload
        import uuid as _uuid
        import services.finance_service as _fs
        execution_result = await _fs.delete_transaction(
            db, _uuid.UUID(workspace_id), _uuid.UUID(p["transaction_id"])
        )

    elif action.action_type == "finance_create_invoice":
        p = action.payload
        import uuid as _uuid
        from datetime import date as _date
        import services.finance_service as _fs
        execution_result = await _fs.create_invoice(
            db,
            _uuid.UUID(workspace_id),
            customer_name=p["customer_name"],
            amount_cents=p["amount_cents"],
            currency=p.get("currency", "INR"),
            issued_on=_date.fromisoformat(p["issued_on"]) if p.get("issued_on") else None,
            due_on=_date.fromisoformat(p["due_on"]) if p.get("due_on") else None,
            notes=p.get("notes"),
            created_by=actor_user_id,
        )

    elif action.action_type == "finance_mark_invoice_paid":
        p = action.payload
        import uuid as _uuid
        from datetime import date as _date
        import services.finance_service as _fs
        execution_result = await _fs.mark_invoice_paid(
            db,
            _uuid.UUID(workspace_id),
            invoice_id=_uuid.UUID(p["invoice_id"]),
            paid_on=_date.fromisoformat(p["paid_on"]) if p.get("paid_on") else None,
            account_id=_uuid.UUID(p["account_id"]) if p.get("account_id") else None,
            created_by=actor_user_id,
        )

    elif action.action_type == "lno_blog_publish":
        p = action.payload
        post_id = p["post_id"]
        supabase_url = _settings.lno_site_supabase_url
        service_key = _settings.lno_site_supabase_service_key
        if not supabase_url or not service_key:
            raise HTTPException(500, "LNO_SITE_SUPABASE_URL or LNO_SITE_SUPABASE_SERVICE_KEY not set")
        sb_headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{supabase_url.rstrip('/')}/rest/v1/posts",
                headers=sb_headers,
                params={"id": f"eq.{post_id}"},
                json={
                    "status": "published",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        if resp.status_code == 401:
            raise HTTPException(500, "Supabase auth failed — check LNO_SITE_SUPABASE_SERVICE_KEY")
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise HTTPException(404, f"Post {post_id} not found — may have been deleted before approval")
        post = data[0] if isinstance(data, list) else data
        execution_result = {
            "published_post_id": post_id,
            "title": p.get("title", ""),
            "slug": post.get("slug") or p.get("slug", ""),
            "published_at": post.get("published_at", ""),
        }
        try:
            from services import site_deploy_service

            deploy = await site_deploy_service.after_blog_publish(workspace_id)
            execution_result["site_deploy"] = deploy
        except Exception as deploy_err:
            execution_result["site_deploy"] = {"ok": False, "error": str(deploy_err)[:500]}

    elif action.action_type == "lno_site_redeploy":
        from services import site_deploy_service

        sync_github = bool(action.payload.get("sync_github", True))
        execution_result = await site_deploy_service.redeploy_lno_site(
            db,
            workspace_id,
            sync_github=sync_github,
        )

    elif action.action_type == "lno_blog_delete":
        p = action.payload
        post_id = p["post_id"]
        supabase_url = _settings.lno_site_supabase_url
        service_key = _settings.lno_site_supabase_service_key
        if not supabase_url or not service_key:
            raise HTTPException(500, "LNO_SITE_SUPABASE_URL or LNO_SITE_SUPABASE_SERVICE_KEY not set")
        sb_headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{supabase_url.rstrip('/')}/rest/v1/posts",
                headers=sb_headers,
                params={"id": f"eq.{post_id}"},
            )
        if resp.status_code == 401:
            raise HTTPException(500, "Supabase auth failed — check LNO_SITE_SUPABASE_SERVICE_KEY")
        resp.raise_for_status()
        execution_result = {"deleted_post_id": post_id, "title": p.get("title", "")}

    else:
        raise HTTPException(400, f"Unknown action_type: {action.action_type}")

    action.status = "executed"
    action.decided_by = actor_user_id
    action.decided_at = datetime.now(timezone.utc)
    action.execution_result = execution_result
    await db.commit()
    return execution_result


async def reject_proposed_action(
    action: ProposedAction,
    db: AsyncSession,
    *,
    actor_user_id: Optional[uuid.UUID],
) -> None:
    if action.status != "pending":
        raise HTTPException(400, f"Action is already {action.status}")
    action.status = "rejected"
    action.decided_by = actor_user_id
    action.decided_at = datetime.now(timezone.utc)
    await db.commit()
