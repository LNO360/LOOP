from sqlalchemy import Column, String, ForeignKey, Text, Boolean, BigInteger, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import uuid
from db.base import Base, TimestampMixin

class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    content = Column(JSONB, nullable=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    linked_channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=True)
    linked_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True)

class File(Base):
    __tablename__ = "files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    uploader_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    message = Column(Text, nullable=False)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Event(Base):
    __tablename__ = "events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    event_metadata = Column("metadata", JSONB, default={})
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class TaskComment(Base, TimestampMixin):
    __tablename__ = "task_comments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)


class WorkspaceMemory(Base):
    """Self-improving AI memory — facts extracted from conversations and stored per workspace."""
    __tablename__ = "workspace_memories"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    key = Column(String, nullable=False)          # e.g. "team.shaan.deadline"
    content = Column(Text, nullable=False)        # e.g. "Shaan owns OLT, deadline June 30"
    importance = Column(Integer, default=3)       # 1-5
    source = Column(String, default="ai")         # "ai", "manual", "message", "doc"
    # Semantic-search embedding (best-effort; may be NULL). Dim must match
    # settings.embedding_dim and the alembic migration.
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("workspace_id", "key", name="uq_workspace_memory_key"),
    )
