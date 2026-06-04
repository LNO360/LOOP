from sqlalchemy import Column, String, ForeignKey, Enum as SAEnum, Date, Text, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid, enum
from db.base import Base, TimestampMixin

class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"

class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.todo, nullable=False)
    priority = Column(SAEnum(TaskPriority), default=TaskPriority.medium, nullable=False)
    source_message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tags = Column(ARRAY(String), default=[])
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True, index=True)


class TaskAssignee(Base):
    """Many-to-many: users assigned to a task."""
    __tablename__ = "task_assignees"
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
