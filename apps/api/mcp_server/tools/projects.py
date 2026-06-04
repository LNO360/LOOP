"""
MCP tools for project operations.

lno_list_projects   — read, executes immediately
lno_create_project  — write, creates proposed_action
lno_update_project  — write, creates proposed_action
"""
import uuid
from typing import Optional
from sqlalchemy import select, func, case
from db.session import AsyncSessionLocal
from models import Project, Task, TaskStatus
from models.agent import ProposedAction
from mcp_server.server import mcp, agent_broadcast


@mcp.tool()
async def lno_list_projects(workspace_id: str) -> list[dict]:
    """List all projects in a workspace with task counts and completion percentage."""
    ws_uuid = uuid.UUID(workspace_id)
    async with AsyncSessionLocal() as db:
        # Single query for task counts per project (avoids N+1)
        counts_result = await db.execute(
            select(
                Task.project_id,
                func.count().label("total"),
                func.count(
                    case((Task.status == TaskStatus.done, 1), else_=None)
                ).label("done_count"),
            )
            .where(Task.workspace_id == ws_uuid)
            .group_by(Task.project_id)
        )
        counts: dict[str, tuple[int, int]] = {
            str(r.project_id): (r.total, r.done_count)
            for r in counts_result.all()
        }

        result = await db.execute(
            select(Project)
            .where(Project.workspace_id == ws_uuid)
            .order_by(Project.created_at.asc())
        )
        projects = result.scalars().all()
        out = []
        for p in projects:
            total, done = counts.get(str(p.id), (0, 0))
            out.append({
                "id": str(p.id),
                "name": p.name,
                "description": p.description,
                "status": p.status,
                "total_tasks": total,
                "done_tasks": done,
                "completion_pct": round(done / total * 100) if total else 0,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })
    await agent_broadcast(workspace_id, "lno_list_projects", "done",
                          f"Found {len(out)} projects")
    return out


@mcp.tool()
async def lno_create_project(
    workspace_id: str,
    name: str,
    description: Optional[str] = None,
    status: str = "active",
    run_id: Optional[str] = None,
) -> dict:
    """
    Propose creating a new project. Creates a pending proposed_action for human approval.
    name: project name (required)
    description: optional project description
    status: "active" | "on_hold" | "completed" (default "active")
    Returns: {"proposed": true, "action_id": "<uuid>", "message": "..."}
    """
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            run_id=uuid.UUID(run_id) if run_id else None,
            action_type="create_project",
            payload={
                "workspace_id": workspace_id,
                "name": name,
                "description": description,
                "status": status,
            },
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        result = {
            "proposed": True,
            "action_id": str(action.id),
            "message": f"Project '{name}' creation queued for approval.",
        }
    await agent_broadcast(workspace_id, "lno_create_project", "done",
                          f"Proposed new project: '{name}'")
    return result


@mcp.tool()
async def lno_update_project(
    workspace_id: str,
    project_id: str,
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """
    Propose updating a project's status, name, or description. Creates a pending proposed_action.
    Returns: {"proposed": true, "action_id": "<uuid>", "message": "..."}
    """
    patch = {}
    if status is not None:
        patch["status"] = status
    if name is not None:
        patch["name"] = name
    if description is not None:
        patch["description"] = description

    if not patch:
        return {"proposed": False, "message": "No fields to update."}

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            run_id=uuid.UUID(run_id) if run_id else None,
            action_type="update_project",
            payload={"workspace_id": workspace_id, "project_id": project_id, "patch": patch},
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        result = {
            "proposed": True,
            "action_id": str(action.id),
            "message": f"Project update on {project_id} queued. Patch: {patch}",
        }
    await agent_broadcast(workspace_id, "lno_update_project", "done",
                          f"Proposed project update on {project_id[:8]}")
    return result
