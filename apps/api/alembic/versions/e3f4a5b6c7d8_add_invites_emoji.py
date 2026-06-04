"""add workspace_invites table and emoji column

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = 'e3f4a5b6c7d8'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add emoji to workspaces
    op.add_column('workspaces', sa.Column('emoji', sa.String(8), nullable=True, server_default='🚀'))

    # Create workspace_invites
    op.create_table(
        'workspace_invites',
        sa.Column('id',           UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by',   UUID(as_uuid=True), sa.ForeignKey('users.id',       ondelete='SET NULL'), nullable=True),
        sa.Column('token',        sa.String(),         nullable=False, unique=True),
        sa.Column('max_uses',     sa.Integer(),        nullable=True),
        sa.Column('use_count',    sa.Integer(),        nullable=False, server_default='0'),
        sa.Column('expires_at',   sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at',   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_workspace_invites_workspace_id', 'workspace_invites', ['workspace_id'])
    op.create_index('ix_workspace_invites_token',        'workspace_invites', ['token'], unique=True)


def downgrade() -> None:
    op.drop_table('workspace_invites')
    op.drop_column('workspaces', 'emoji')
