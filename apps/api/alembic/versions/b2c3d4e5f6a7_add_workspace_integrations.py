"""add workspace_integrations table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-26 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'workspace_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True),
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('access_token', sa.Text, nullable=True),
        sa.Column('refresh_token', sa.Text, nullable=True),
        sa.Column('token_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scopes', sa.Text, nullable=True),
        sa.Column('account_email', sa.String(255), nullable=True),
        sa.Column('api_key', sa.Text, nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'provider', name='uq_workspace_provider'),
    )
    op.create_index('ix_workspace_integrations_workspace_id',
                    'workspace_integrations', ['workspace_id'])


def downgrade() -> None:
    op.drop_index('ix_workspace_integrations_workspace_id',
                  table_name='workspace_integrations')
    op.drop_table('workspace_integrations')
