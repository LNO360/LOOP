"""
GithubWebhookEvent   — one row per inbound GitHub App webhook delivery
GithubAppInstallation — maps installation_id → workspace_id
"""
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from db.base import Base


class GithubWebhookEvent(Base):
    __tablename__ = "github_webhook_events"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id     = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True)
    installation_id  = Column(String, nullable=False, index=True)
    delivery_id      = Column(String, unique=True, nullable=False)
    event_type       = Column(String, nullable=False)          # X-GitHub-Event
    action           = Column(String, nullable=True)           # payload .action
    repo_full_name   = Column(String, nullable=True)           # owner/repo
    payload          = Column(JSONB, nullable=False, default={})
    status           = Column(String, nullable=False, default="received", index=True)
    # status values: received | processing | done | skipped | error
    agent_run_id     = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)
    error            = Column(Text, nullable=True)
    received_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at     = Column(DateTime(timezone=True), nullable=True)


class GithubAppInstallation(Base):
    __tablename__ = "github_app_installations"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id    = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    installation_id = Column(String, nullable=False)
    account_login   = Column(String, nullable=False)
    installed_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("workspace_id", "installation_id", name="uq_workspace_installation"),)
