"""agent_infrastructure

Revision ID: 78dbb0b8fde7
Revises: 5e6f29c84a9f
Create Date: 2026-05-25 19:57:43.416990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '78dbb0b8fde7'
down_revision: Union[str, None] = '5e6f29c84a9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id"), nullable=True),
        sa.Column("trigger_type", sa.String(), nullable=False),
        sa.Column("trigger_payload", postgresql.JSONB(), nullable=True),
        sa.Column("agent_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tool_calls_json", postgresql.JSONB(), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_agent_runs_workspace_id", "agent_runs", ["workspace_id"])
    op.create_table(
        "proposed_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("risk_level", sa.String(), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("proposed_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("execution_result", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_proposed_actions_workspace_id", "proposed_actions", ["workspace_id"])
    op.create_index("ix_proposed_actions_status", "proposed_actions", ["status"])


def downgrade() -> None:
    op.drop_table("proposed_actions")
    op.drop_table("agent_runs")
