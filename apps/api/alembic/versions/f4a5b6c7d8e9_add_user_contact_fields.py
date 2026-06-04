"""add phone, telegram_username, telegram_user_id to users

Revision ID: f4a5b6c7d8e9
Revises: ec6efd2b7d40
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'f4a5b6c7d8e9'
down_revision = 'ec6efd2b7d40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone',             sa.String(32),  nullable=True))
    op.add_column('users', sa.Column('telegram_username', sa.String(64),  nullable=True))
    op.add_column('users', sa.Column('telegram_user_id',  sa.String(32),  nullable=True))
    op.create_index('ix_users_telegram_user_id', 'users', ['telegram_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_users_telegram_user_id', table_name='users')
    op.drop_column('users', 'telegram_user_id')
    op.drop_column('users', 'telegram_username')
    op.drop_column('users', 'phone')
