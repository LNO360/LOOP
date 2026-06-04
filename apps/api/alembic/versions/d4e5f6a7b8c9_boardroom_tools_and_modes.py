"""add boardroom debate_mode, default_tools, and per-agent tools

Revision ID: d4e5f6a7b8c9
Revises: b3c4d5e6f7a8
Create Date: 2026-05-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d4e5f6a7b8c9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "boardroom_sessions",
        sa.Column(
            "debate_mode",
            sa.String(20),
            nullable=False,
            server_default="round_robin",
        ),
    )
    op.add_column(
        "boardroom_sessions",
        sa.Column(
            "default_tools",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "boardroom_agents",
        sa.Column("tools", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("boardroom_agents", "tools")
    op.drop_column("boardroom_sessions", "default_tools")
    op.drop_column("boardroom_sessions", "debate_mode")
