"""add_agent_teams

Revision ID: 18065f96ebf2
Revises: c1d2e3f4a5b6
Create Date: 2026-05-26 19:57:34.918578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '18065f96ebf2'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agent_teams table
    op.create_table('agent_teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_teams_workspace_id', 'agent_teams', ['workspace_id'])

    # Create agent_team_members table with TeamRole enum
    op.create_table('agent_team_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('team_role', sa.Enum('coordinator', 'specialist', name='teamrole'), nullable=False, server_default='specialist'),
        sa.ForeignKeyConstraint(['team_id'], ['agent_teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['user_agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'agent_id', name='uq_team_member'),
    )
    op.create_index('ix_agent_team_members_team_id', 'agent_team_members', ['team_id'])
    op.create_index('ix_agent_team_members_agent_id', 'agent_team_members', ['agent_id'])


def downgrade():
    op.drop_index('ix_agent_teams_workspace_id')
    op.drop_index('ix_agent_team_members_team_id')
    op.drop_index('ix_agent_team_members_agent_id')
    op.drop_table('agent_team_members')
    op.drop_table('agent_teams')
    op.execute("DROP TYPE IF EXISTS teamrole")
