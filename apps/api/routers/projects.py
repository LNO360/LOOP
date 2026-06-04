from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from db.session import get_db
from models import Project, Task, User
from core.auth import get_current_user
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/workspaces/{workspace_id}/projects", tags=["projects"])

def _project_out(p: Project) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "status": p.status,
        "created_by": str(p.created_by) if p.created_by else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }

class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = None

class UpdateProjectRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class DeleteProjectRequest(BaseModel):
    """Safety: must match project name exactly; acknowledge task unlink if any."""
    confirm_name: str
    acknowledge_tasks: bool = False

@router.get("")
async def list_projects(workspace_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.workspace_id == uuid.UUID(workspace_id)).order_by(Project.created_at.asc()))
    return [_project_out(p) for p in result.scalars().all()]

@router.get("/{project_id}")
async def get_project(workspace_id: str, project_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.workspace_id == uuid.UUID(workspace_id)))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Project not found")
    return _project_out(p)

@router.post("")
async def create_project(workspace_id: str, body: CreateProjectRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    p = Project(
        workspace_id=uuid.UUID(workspace_id),
        name=body.name,
        description=body.description,
        status=body.status or "active",
        created_by=current_user.id,
    )
    db.add(p)
    await db.commit()
    return _project_out(p)

@router.patch("/{project_id}")
async def update_project(workspace_id: str, project_id: str, body: UpdateProjectRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Project).where(Project.id == uuid.UUID(project_id), Project.workspace_id == uuid.UUID(workspace_id)))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Project not found")
    if body.name is not None: p.name = body.name
    if body.description is not None: p.description = body.description
    if body.status is not None: p.status = body.status
    await db.commit()
    return _project_out(p)


@router.delete("/{project_id}")
async def delete_project(
    workspace_id: str,
    project_id: str,
    body: DeleteProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a project. Requires typing the exact project name.
    Linked tasks are unlinked (not deleted) only after explicit acknowledgement.
    """
    workspace_uuid = uuid.UUID(workspace_id)
    project_uuid = uuid.UUID(project_id)

    result = await db.execute(
        select(Project).where(Project.id == project_uuid, Project.workspace_id == workspace_uuid)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")

    if body.confirm_name.strip() != project.name:
        raise HTTPException(
            400,
            detail="Confirmation failed: type the exact project name to delete this project.",
        )

    count_result = await db.execute(
        select(func.count()).select_from(Task).where(
            Task.workspace_id == workspace_uuid,
            Task.project_id == project_uuid,
        )
    )
    task_count = int(count_result.scalar() or 0)

    if task_count > 0 and not body.acknowledge_tasks:
        raise HTTPException(
            409,
            detail={
                "message": (
                    f"This project has {task_count} linked task(s). "
                    "Check the acknowledgement box to unlink them and delete the project."
                ),
                "task_count": task_count,
                "requires_acknowledge_tasks": True,
            },
        )

    unlinked = 0
    if task_count > 0:
        unlink_result = await db.execute(
            update(Task)
            .where(Task.workspace_id == workspace_uuid, Task.project_id == project_uuid)
            .values(project_id=None)
        )
        unlinked = unlink_result.rowcount or task_count

    await db.delete(project)
    await db.commit()

    return {
        "ok": True,
        "deleted_project_id": str(project_uuid),
        "unlinked_tasks": unlinked,
    }
