from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models import Document, User
from core.auth import get_current_user
from pydantic import BaseModel
from typing import Optional, Any
import uuid

router = APIRouter(prefix="/workspaces/{workspace_id}/documents", tags=["documents"])

class DocumentRequest(BaseModel):
    title: str
    content: Optional[Any] = None
    linked_channel_id: Optional[str] = None
    linked_task_id: Optional[str] = None

@router.get("")
async def list_documents(workspace_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Document).where(Document.workspace_id == uuid.UUID(workspace_id)))
    return [{"id": str(d.id), "title": d.title, "author_id": str(d.author_id), "created_at": d.created_at.isoformat()} for d in result.scalars().all()]

@router.post("")
async def create_document(workspace_id: str, body: DocumentRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    d = Document(
        workspace_id=uuid.UUID(workspace_id), title=body.title, content=body.content,
        author_id=current_user.id,
        linked_channel_id=uuid.UUID(body.linked_channel_id) if body.linked_channel_id else None,
        linked_task_id=uuid.UUID(body.linked_task_id) if body.linked_task_id else None,
    )
    db.add(d)
    await db.commit()
    return {"id": str(d.id), "title": d.title}

@router.get("/{document_id}")
async def get_document(workspace_id: str, document_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Document not found")
    return {"id": str(d.id), "title": d.title, "content": d.content, "author_id": str(d.author_id), "created_at": d.created_at.isoformat()}

@router.patch("/{document_id}")
async def update_document(workspace_id: str, document_id: str, body: DocumentRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(404)
    d.title = body.title
    if body.content is not None:
        d.content = body.content
    await db.commit()
    return {"id": str(d.id), "title": d.title}
