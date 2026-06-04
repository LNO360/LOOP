"""add user_agents table for custom Hermes agents

Revision ID: a1b2c3d4e5f6
Revises: 78dbb0b8fde7
Create Date: 2026-05-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f6'
down_revision = '78dbb0b8fde7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),

        # Identity
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('slug', sa.String(80), nullable=False),
        sa.Column('avatar_emoji', sa.String(8), server_default='🤖', nullable=False),
        sa.Column('description', sa.Text, nullable=True),

        # Personality — full SOUL.md content
        sa.Column('soul_md', sa.Text, nullable=False),

        # Schedule — cron expression or human schedule ("every 2 hours", "0 9 * * 1")
        sa.Column('schedule', sa.String(100), nullable=True),

        # Model override (defaults to workspace/Hermes default)
        sa.Column('model', sa.String(120), nullable=True),

        # Extra tools/skills to load (comma-separated)
        sa.Column('extra_skills', sa.Text, nullable=True),

        # State
        sa.Column('active', sa.Boolean, server_default='true', nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer, server_default='0', nullable=False),

        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'slug', name='uq_user_agent_workspace_slug'),
    )
    op.create_index('ix_user_agents_workspace', 'user_agents', ['workspace_id'])


def downgrade() -> None:
    op.drop_index('ix_user_agents_workspace', table_name='user_agents')
    op.drop_table('user_agents')
