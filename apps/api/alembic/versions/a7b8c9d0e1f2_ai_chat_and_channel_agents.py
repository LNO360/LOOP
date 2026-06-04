"""ai chat conversations + channel agent messages/sessions

Revision ID: a7b8c9d0e1f2
Revises: f4a5b6c7d8e9
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a7b8c9d0e1f2'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ai_conversations ──────────────────────────────────────────────
    op.create_table(
        'ai_conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('workspace_id', UUID(as_uuid=True), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hermes_session_id', sa.String(), nullable=True),
        sa.Column('agent_slug', sa.String(80), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_ai_conversations_workspace_id', 'ai_conversations', ['workspace_id'])
    op.create_index('ix_ai_conversations_user_id', 'ai_conversations', ['user_id'])

    # ── ai_chat_messages ──────────────────────────────────────────────
    op.create_table(
        'ai_chat_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', UUID(as_uuid=True), sa.ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('tool_calls', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_ai_chat_messages_conversation_id', 'ai_chat_messages', ['conversation_id'])

    # ── channel_agent_sessions ────────────────────────────────────────
    op.create_table(
        'channel_agent_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_id', UUID(as_uuid=True), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_slug', sa.String(80), nullable=False),
        sa.Column('hermes_session_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('channel_id', 'agent_slug', name='uq_channel_agent'),
    )
    op.create_index('ix_channel_agent_sessions_channel_id', 'channel_agent_sessions', ['channel_id'])

    # ── messages: agent authorship ────────────────────────────────────
    op.alter_column('messages', 'author_id', existing_type=UUID(as_uuid=True), nullable=True)
    op.add_column('messages', sa.Column('sender_type', sa.String(), nullable=False, server_default='user'))
    op.add_column('messages', sa.Column('agent_slug', sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column('messages', 'agent_slug')
    op.drop_column('messages', 'sender_type')
    op.alter_column('messages', 'author_id', existing_type=UUID(as_uuid=True), nullable=False)

    op.drop_index('ix_channel_agent_sessions_channel_id', table_name='channel_agent_sessions')
    op.drop_table('channel_agent_sessions')

    op.drop_index('ix_ai_chat_messages_conversation_id', table_name='ai_chat_messages')
    op.drop_table('ai_chat_messages')

    op.drop_index('ix_ai_conversations_user_id', table_name='ai_conversations')
    op.drop_index('ix_ai_conversations_workspace_id', table_name='ai_conversations')
    op.drop_table('ai_conversations')
