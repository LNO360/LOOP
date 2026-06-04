from fastapi import APIRouter, Depends, UploadFile, File as FastAPIFile
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_db
from models import File, User
from core.auth import get_current_user
from services.storage import upload_file_to_s3
import uuid

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload")
async def upload(
    workspace_id: str,
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = await file.read()
    file_id = str(uuid.uuid4())
    key = f"{workspace_id}/{file_id}/{file.filename}"
    url = await upload_file_to_s3(key, content, file.content_type or "application/octet-stream")
    f = File(
        workspace_id=uuid.UUID(workspace_id),
        uploader_id=current_user.id,
        name=file.filename,
        url=url,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=len(content)
    )
    db.add(f)
    await db.commit()
    return {"id": str(f.id), "url": url, "name": file.filename}
