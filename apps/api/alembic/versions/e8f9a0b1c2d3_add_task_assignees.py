"""add task_assignees junction table

Revision ID: e8f9a0b1c2d3
Revises: 15b94bece58a
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e8f9a0b1c2d3"
down_revision = "15b94bece58a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_assignees",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "user_id"),
    )
    op.create_index("ix_task_assignees_user_id", "task_assignees", ["user_id"])

    # Backfill from legacy tasks.assignee_id
    op.execute(
        """
        INSERT INTO task_assignees (task_id, user_id)
        SELECT id, assignee_id FROM tasks
        WHERE assignee_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_task_assignees_user_id", table_name="task_assignees")
    op.drop_table("task_assignees")
