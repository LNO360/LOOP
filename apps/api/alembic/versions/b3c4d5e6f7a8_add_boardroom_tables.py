"""add boardroom_sessions and boardroom_agents tables

Revision ID: b3c4d5e6f7a8
Revises: a7b8c9d0e1f2
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "b3c4d5e6f7a8"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boardroom_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("topic", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="setup"),
        sa.Column("rounds_config", sa.Integer, nullable=False, server_default="2"),
        sa.Column("transcript", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_boardroom_sessions_workspace_id",
        "boardroom_sessions",
        ["workspace_id"],
    )

    op.create_table(
        "boardroom_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("boardroom_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("emoji", sa.String(8), nullable=False, server_default="🤖"),
        sa.Column("persona_type", sa.String(20), nullable=False),
        sa.Column("agent_ref", UUID(as_uuid=True), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("turn_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_boardroom_agents_session_id",
        "boardroom_agents",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_boardroom_agents_session_id", table_name="boardroom_agents")
    op.drop_table("boardroom_agents")
    op.drop_index(
        "ix_boardroom_sessions_workspace_id", table_name="boardroom_sessions"
    )
    op.drop_table("boardroom_sessions")
