"""Finance models: settings, accounts, categories, transactions, invoices, snapshots."""
import enum
import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, Enum as SAEnum,
    ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from db.base import Base, TimestampMixin


class FinanceAccountType(str, enum.Enum):
    cash = "cash"
    bank = "bank"
    other = "other"


class FinanceCategoryKind(str, enum.Enum):
    income = "income"
    expense = "expense"


class FinanceDirection(str, enum.Enum):
    income = "income"
    expense = "expense"


class FinanceTransactionSource(str, enum.Enum):
    manual = "manual"
    import_ = "import"
    agent = "agent"


class FinanceInvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    void = "void"


class WorkspaceFinanceSettings(Base, TimestampMixin):
    __tablename__ = "workspace_finance_settings"

    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    base_currency = Column(String(3), nullable=False, default="INR")
    fiscal_year_start_month = Column(Integer, nullable=False, default=1)


class FinanceAccount(Base, TimestampMixin):
    __tablename__ = "finance_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    type = Column(SAEnum(FinanceAccountType), nullable=False, default=FinanceAccountType.bank)
    opening_balance_cents = Column(BigInteger, nullable=False, default=0)
    opening_balance_date = Column(Date, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class FinanceCategory(Base, TimestampMixin):
    __tablename__ = "finance_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    kind = Column(SAEnum(FinanceCategoryKind), nullable=False)
    is_system = Column(Boolean, nullable=False, default=False)
    sort_order = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_finance_category_ws_name"),
    )


class FinanceTransaction(Base, TimestampMixin):
    __tablename__ = "finance_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False
    )
    account_id = Column(
        UUID(as_uuid=True), ForeignKey("finance_accounts.id"), nullable=False
    )
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("finance_categories.id"), nullable=True
    )
    direction = Column(SAEnum(FinanceDirection), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    occurred_on = Column(Date, nullable=False)
    description = Column(String(500), nullable=False, default="")
    reference = Column(String(255), nullable=True)
    source = Column(
        SAEnum(FinanceTransactionSource, name="financetransactionsource"),
        nullable=False,
        default=FinanceTransactionSource.manual,
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        Index("ix_fin_tx_ws_date", "workspace_id", "occurred_on"),
        Index("ix_fin_tx_ws_cat", "workspace_id", "category_id"),
    )


class FinanceInvoice(Base, TimestampMixin):
    __tablename__ = "finance_invoices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    customer_name = Column(String(255), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    issued_on = Column(Date, nullable=True)
    due_on = Column(Date, nullable=True)
    status = Column(
        SAEnum(FinanceInvoiceStatus), nullable=False, default=FinanceInvoiceStatus.draft
    )
    paid_on = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    linked_transaction_id = Column(
        UUID(as_uuid=True), ForeignKey("finance_transactions.id"), nullable=True
    )
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class FinanceSnapshot(Base):
    """Monthly precomputed rollups for fast overview + agent queries."""
    __tablename__ = "finance_snapshots"

    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    period = Column(String(7), primary_key=True)  # YYYY-MM
    revenue_cents = Column(BigInteger, nullable=False, default=0)
    expense_cents = Column(BigInteger, nullable=False, default=0)
