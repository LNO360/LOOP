"""add finance tables

Revision ID: c1d2e3f4a5b6
Revises: b2c3d4e5f6a7
Create Date: 2026-05-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c1d2e3f4a5b6'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── ENUMs ─────────────────────────────────────────────────────────────────
    op.execute("CREATE TYPE financeaccounttype AS ENUM ('cash', 'bank', 'other')")
    op.execute("CREATE TYPE financecategorykind AS ENUM ('income', 'expense')")
    op.execute("CREATE TYPE financedirection AS ENUM ('income', 'expense')")
    op.execute("CREATE TYPE financetransactionsource AS ENUM ('manual', 'import', 'agent')")
    op.execute("CREATE TYPE financeinvoicestatus AS ENUM ('draft', 'sent', 'paid', 'void')")

    # ── workspace_finance_settings ────────────────────────────────────────────
    op.create_table(
        'workspace_finance_settings',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), primary_key=True),
        sa.Column('base_currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('fiscal_year_start_month', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # ── finance_accounts ──────────────────────────────────────────────────────
    op.create_table(
        'finance_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('type', sa.Enum('cash', 'bank', 'other', name='financeaccounttype'), nullable=False, server_default='bank'),
        sa.Column('opening_balance_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('opening_balance_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_finance_accounts_workspace', 'finance_accounts', ['workspace_id'])

    # ── finance_categories ────────────────────────────────────────────────────
    op.create_table(
        'finance_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('kind', sa.Enum('income', 'expense', name='financecategorykind'), nullable=False),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_finance_category_ws_name'),
    )
    op.create_index('ix_finance_categories_workspace', 'finance_categories', ['workspace_id'])

    # ── finance_transactions ──────────────────────────────────────────────────
    op.create_table(
        'finance_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('finance_accounts.id'), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('finance_categories.id'), nullable=True),
        sa.Column('direction', sa.Enum('income', 'expense', name='financedirection'), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('occurred_on', sa.Date(), nullable=False),
        sa.Column('description', sa.String(500), nullable=False, server_default=''),
        sa.Column('reference', sa.String(255), nullable=True),
        sa.Column('source', sa.Enum('manual', 'import', 'agent', name='financetransactionsource'), nullable=False, server_default='manual'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_fin_tx_ws_date', 'finance_transactions', ['workspace_id', 'occurred_on'])
    op.create_index('ix_fin_tx_ws_cat', 'finance_transactions', ['workspace_id', 'category_id'])

    # ── finance_invoices ──────────────────────────────────────────────────────
    op.create_table(
        'finance_invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('amount_cents', sa.BigInteger(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('issued_on', sa.Date(), nullable=True),
        sa.Column('due_on', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'sent', 'paid', 'void', name='financeinvoicestatus'), nullable=False, server_default='draft'),
        sa.Column('paid_on', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('linked_transaction_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('finance_transactions.id'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_finance_invoices_workspace', 'finance_invoices', ['workspace_id'])

    # ── finance_snapshots ─────────────────────────────────────────────────────
    op.create_table(
        'finance_snapshots',
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workspaces.id'), primary_key=True),
        sa.Column('period', sa.String(7), primary_key=True),  # YYYY-MM
        sa.Column('revenue_cents', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('expense_cents', sa.BigInteger(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('finance_snapshots')
    op.drop_table('finance_invoices')
    op.drop_index('ix_fin_tx_ws_cat', 'finance_transactions')
    op.drop_index('ix_fin_tx_ws_date', 'finance_transactions')
    op.drop_table('finance_transactions')
    op.drop_index('ix_finance_categories_workspace', 'finance_categories')
    op.drop_table('finance_categories')
    op.drop_index('ix_finance_accounts_workspace', 'finance_accounts')
    op.drop_table('finance_accounts')
    op.drop_table('workspace_finance_settings')
    op.execute("DROP TYPE IF EXISTS financeinvoicestatus")
    op.execute("DROP TYPE IF EXISTS financetransactionsource")
    op.execute("DROP TYPE IF EXISTS financedirection")
    op.execute("DROP TYPE IF EXISTS financecategorykind")
    op.execute("DROP TYPE IF EXISTS financeaccounttype")
