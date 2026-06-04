from sqlalchemy import Column, String, ForeignKey, Enum as SAEnum, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid, enum
from db.base import Base, TimestampMixin

class MemberRole(str, enum.Enum):
    admin = "admin"
    member = "member"
    viewer = "viewer"

class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    emoji    = Column(String(8), nullable=True, default="🚀")

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role = Column(SAEnum(MemberRole), default=MemberRole.member, nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
