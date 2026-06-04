"""add github webhook tables

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "github_app_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installation_id", sa.String(), nullable=False),
        sa.Column("account_login", sa.String(), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("installation_id", name="uq_github_app_installation_id"),
        sa.UniqueConstraint("workspace_id", "installation_id", name="uq_workspace_installation"),
    )
    op.create_index("ix_github_app_installations_workspace_id",
                    "github_app_installations", ["workspace_id"])

    op.create_table(
        "github_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("installation_id", sa.String(), nullable=False),
        sa.Column("delivery_id", sa.String(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=True),
        sa.Column("repo_full_name", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="received"),
        sa.Column("agent_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_github_webhook_events_workspace_id",
                    "github_webhook_events", ["workspace_id"])
    op.create_index("ix_github_webhook_events_status",
                    "github_webhook_events", ["status"])
    op.create_index("ix_github_webhook_events_installation_id",
                    "github_webhook_events", ["installation_id"])


def downgrade() -> None:
    op.drop_table("github_webhook_events")
    op.drop_table("github_app_installations")
