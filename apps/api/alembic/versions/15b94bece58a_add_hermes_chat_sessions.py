"""add_hermes_chat_sessions

Revision ID: 15b94bece58a
Revises: f5a6b7c8d9e0
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "15b94bece58a"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hermes_chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_slug", sa.String(length=80), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_tail", postgresql.JSONB(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", "agent_slug", name="uq_hermes_chat_session"),
    )
    op.create_index("ix_hermes_chat_sessions_workspace_id", "hermes_chat_sessions", ["workspace_id"])
    op.create_index("ix_hermes_chat_sessions_user_id", "hermes_chat_sessions", ["user_id"])
    op.create_index(
        "uq_hermes_base_session",
        "hermes_chat_sessions",
        ["workspace_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("agent_slug IS NULL"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_hermes_base_session")
    op.drop_index("ix_hermes_chat_sessions_user_id", table_name="hermes_chat_sessions")
    op.drop_index("ix_hermes_chat_sessions_workspace_id", table_name="hermes_chat_sessions")
    op.drop_table("hermes_chat_sessions")
