# apps/api/models/invite.py
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db.base import Base


class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id= Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by  = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    token       = Column(String, unique=True, nullable=False, index=True)
    max_uses    = Column(Integer, nullable=True)          # None = unlimited
    use_count   = Column(Integer, nullable=False, default=0)
    expires_at  = Column(DateTime(timezone=True), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
