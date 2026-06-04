from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models import TaskComment, User
from core.auth import get_current_user
from pydantic import BaseModel
import uuid

router = APIRouter(
    prefix="/workspaces/{workspace_id}/tasks/{task_id}/comments",
    tags=["task-comments"]
)

class CreateCommentRequest(BaseModel):
    content: str

@router.get("")
async def list_comments(
    workspace_id: str,
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TaskComment, User)
        .join(User, TaskComment.author_id == User.id)
        .where(TaskComment.task_id == uuid.UUID(task_id))
        .order_by(TaskComment.created_at)
    )
    return [
        {
            "id": str(c.id),
            "content": c.content,
            "author_id": str(c.author_id),
            "author_name": u.name,
            "created_at": c.created_at.isoformat(),
        }
        for c, u in result.all()
    ]

@router.post("")
async def create_comment(
    workspace_id: str,
    task_id: str,
    body: CreateCommentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = TaskComment(
        task_id=uuid.UUID(task_id),
        author_id=current_user.id,
        content=body.content,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return {
        "id": str(comment.id),
        "content": comment.content,
        "author_id": str(comment.author_id),
        "author_name": current_user.name,
        "created_at": comment.created_at.isoformat(),
    }

@router.delete("/{comment_id}")
async def delete_comment(
    workspace_id: str,
    task_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TaskComment).where(TaskComment.id == uuid.UUID(comment_id))
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(404, "Comment not found")
    if comment.author_id != current_user.id:
        raise HTTPException(403, "Not your comment")
    await db.delete(comment)
    await db.commit()
    return {"ok": True}
