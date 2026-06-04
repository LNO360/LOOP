"""
Finance service — CRUD, summaries, cash position, CSV import.
Used by both REST routers (direct writes) and MCP tools (proposed_actions for writes).
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.finance import (
    FinanceAccount,
    FinanceAccountType,
    FinanceCategory,
    FinanceCategoryKind,
    FinanceDirection,
    FinanceInvoice,
    FinanceInvoiceStatus,
    FinanceSnapshot,
    FinanceTransaction,
    FinanceTransactionSource,
    WorkspaceFinanceSettings,
)

# ── System seed categories ────────────────────────────────────────────────────

_SEED_CATEGORIES = [
    ("Revenue", FinanceCategoryKind.income, 0),
    ("Other income", FinanceCategoryKind.income, 1),
    ("Payroll", FinanceCategoryKind.expense, 10),
    ("Rent", FinanceCategoryKind.expense, 11),
    ("SaaS", FinanceCategoryKind.expense, 12),
    ("Marketing", FinanceCategoryKind.expense, 13),
    ("Travel", FinanceCategoryKind.expense, 14),
    ("Office", FinanceCategoryKind.expense, 15),
    ("Other expense", FinanceCategoryKind.expense, 99),
]


async def ensure_finance_setup(db: AsyncSession, workspace_id: uuid.UUID) -> None:
    """
    Idempotent: create settings row + seed categories if not present.
    Call on first finance API access or workspace create.
    """
    # Settings
    existing = await db.execute(
        select(WorkspaceFinanceSettings).where(
            WorkspaceFinanceSettings.workspace_id == workspace_id
        )
    )
    if not existing.scalar_one_or_none():
        db.add(WorkspaceFinanceSettings(workspace_id=workspace_id))

    # Categories
    for name, kind, order in _SEED_CATEGORIES:
        res = await db.execute(
            select(FinanceCategory).where(
                FinanceCategory.workspace_id == workspace_id,
                FinanceCategory.name == name,
            )
        )
        if not res.scalar_one_or_none():
            db.add(FinanceCategory(
                workspace_id=workspace_id,
                name=name,
                kind=kind,
                sort_order=order,
                is_system=True,
            ))
    await db.flush()


# ── Settings ─────────────────────────────────────────────────────────────────

async def get_settings(db: AsyncSession, workspace_id: uuid.UUID) -> dict:
    await ensure_finance_setup(db, workspace_id)
    res = await db.execute(
        select(WorkspaceFinanceSettings).where(
            WorkspaceFinanceSettings.workspace_id == workspace_id
        )
    )
    s = res.scalar_one()
    return {
        "workspace_id": str(workspace_id),
        "base_currency": s.base_currency,
        "fiscal_year_start_month": s.fiscal_year_start_month,
    }


async def update_settings(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    base_currency: Optional[str],
    fiscal_year_start_month: Optional[int],
) -> dict:
    await ensure_finance_setup(db, workspace_id)
    res = await db.execute(
        select(WorkspaceFinanceSettings).where(
            WorkspaceFinanceSettings.workspace_id == workspace_id
        )
    )
    s = res.scalar_one()
    if base_currency:
        s.base_currency = base_currency.upper()
    if fiscal_year_start_month:
        s.fiscal_year_start_month = fiscal_year_start_month
    await db.commit()
    return await get_settings(db, workspace_id)


# ── Accounts ─────────────────────────────────────────────────────────────────

async def _account_balance(db: AsyncSession, account: FinanceAccount) -> int:
    """Compute current balance for an account (opening + flows)."""
    res = await db.execute(
        select(
            func.coalesce(func.sum(
                func.case(
                    (FinanceTransaction.direction == FinanceDirection.income, FinanceTransaction.amount_cents),
                    else_=-FinanceTransaction.amount_cents,
                )
            ), 0)
        ).where(
            FinanceTransaction.account_id == account.id,
            FinanceTransaction.workspace_id == account.workspace_id,
        )
    )
    net = int(res.scalar() or 0)
    return account.opening_balance_cents + net


def _account_out(account: FinanceAccount, balance_cents: int) -> dict:
    return {
        "id": str(account.id),
        "workspace_id": str(account.workspace_id),
        "name": account.name,
        "type": account.type.value,
        "opening_balance_cents": account.opening_balance_cents,
        "opening_balance_date": account.opening_balance_date.isoformat() if account.opening_balance_date else None,
        "balance_cents": balance_cents,
        "is_active": account.is_active,
        "notes": account.notes,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


async def list_accounts(db: AsyncSession, workspace_id: uuid.UUID) -> list[dict]:
    await ensure_finance_setup(db, workspace_id)
    res = await db.execute(
        select(FinanceAccount).where(FinanceAccount.workspace_id == workspace_id)
        .order_by(FinanceAccount.created_at)
    )
    accounts = res.scalars().all()
    out = []
    for acc in accounts:
        bal = await _account_balance(db, acc)
        out.append(_account_out(acc, bal))
    return out


async def create_account(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    type: str,
    opening_balance_cents: int = 0,
    opening_balance_date: Optional[date] = None,
    notes: Optional[str] = None,
    created_by: Optional[uuid.UUID] = None,
) -> dict:
    await ensure_finance_setup(db, workspace_id)
    acc = FinanceAccount(
        workspace_id=workspace_id,
        name=name,
        type=FinanceAccountType(type),
        opening_balance_cents=opening_balance_cents,
        opening_balance_date=opening_balance_date,
        notes=notes,
        created_by=created_by,
    )
    db.add(acc)
    await db.flush()
    await db.commit()
    return _account_out(acc, opening_balance_cents)


async def update_account(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    **kwargs,
) -> dict:
    res = await db.execute(
        select(FinanceAccount).where(
            FinanceAccount.id == account_id,
            FinanceAccount.workspace_id == workspace_id,
        )
    )
    acc = res.scalar_one_or_none()
    if not acc:
        raise ValueError(f"Account {account_id} not found")
    for k, v in kwargs.items():
        if v is not None and hasattr(acc, k):
            setattr(acc, k, v)
    await db.commit()
    bal = await _account_balance(db, acc)
    return _account_out(acc, bal)


async def deactivate_account(db: AsyncSession, workspace_id: uuid.UUID, account_id: uuid.UUID) -> dict:
    return await update_account(db, workspace_id, account_id, is_active=False)


# ── Categories ────────────────────────────────────────────────────────────────

def _cat_out(c: FinanceCategory) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "kind": c.kind.value,
        "is_system": c.is_system,
        "sort_order": c.sort_order,
    }


async def list_categories(db: AsyncSession, workspace_id: uuid.UUID) -> list[dict]:
    await ensure_finance_setup(db, workspace_id)
    res = await db.execute(
        select(FinanceCategory).where(FinanceCategory.workspace_id == workspace_id)
        .order_by(FinanceCategory.sort_order, FinanceCategory.name)
    )
    return [_cat_out(c) for c in res.scalars().all()]


async def create_category(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    name: str,
    kind: str,
) -> dict:
    await ensure_finance_setup(db, workspace_id)
    cat = FinanceCategory(
        workspace_id=workspace_id,
        name=name,
        kind=FinanceCategoryKind(kind),
        is_system=False,
        sort_order=50,
    )
    db.add(cat)
    await db.flush()
    await db.commit()
    return _cat_out(cat)


# ── Transactions ──────────────────────────────────────────────────────────────

def _tx_out(t: FinanceTransaction) -> dict:
    return {
        "id": str(t.id),
        "workspace_id": str(t.workspace_id),
        "account_id": str(t.account_id),
        "category_id": str(t.category_id) if t.category_id else None,
        "direction": t.direction.value,
        "amount_cents": t.amount_cents,
        "currency": t.currency,
        "occurred_on": t.occurred_on.isoformat() if t.occurred_on else None,
        "description": t.description,
        "reference": t.reference,
        "source": t.source.value,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


async def list_transactions(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    category_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    direction: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    q = select(FinanceTransaction).where(
        FinanceTransaction.workspace_id == workspace_id
    )
    if from_date:
        q = q.where(FinanceTransaction.occurred_on >= from_date)
    if to_date:
        q = q.where(FinanceTransaction.occurred_on <= to_date)
    if category_id:
        q = q.where(FinanceTransaction.category_id == category_id)
    if account_id:
        q = q.where(FinanceTransaction.account_id == account_id)
    if direction:
        q = q.where(FinanceTransaction.direction == FinanceDirection(direction))
    q = q.order_by(FinanceTransaction.occurred_on.desc()).limit(limit)
    res = await db.execute(q)
    return [_tx_out(t) for t in res.scalars().all()]


async def create_transaction(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    account_id: uuid.UUID,
    direction: str,
    amount_cents: int,
    occurred_on: date,
    description: str,
    currency: str = "INR",
    category_id: Optional[uuid.UUID] = None,
    reference: Optional[str] = None,
    source: str = "manual",
    created_by: Optional[uuid.UUID] = None,
) -> dict:
    tx = FinanceTransaction(
        workspace_id=workspace_id,
        account_id=account_id,
        category_id=category_id,
        direction=FinanceDirection(direction),
        amount_cents=abs(amount_cents),
        currency=currency,
        occurred_on=occurred_on,
        description=description,
        reference=reference,
        source=FinanceTransactionSource(source),
        created_by=created_by,
    )
    db.add(tx)
    await db.flush()
    await _rebuild_snapshot(db, workspace_id, occurred_on)
    await db.commit()
    return _tx_out(tx)


async def update_transaction(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    tx_id: uuid.UUID,
    **kwargs,
) -> dict:
    res = await db.execute(
        select(FinanceTransaction).where(
            FinanceTransaction.id == tx_id,
            FinanceTransaction.workspace_id == workspace_id,
        )
    )
    tx = res.scalar_one_or_none()
    if not tx:
        raise ValueError(f"Transaction {tx_id} not found")
    old_date = tx.occurred_on
    for k, v in kwargs.items():
        if v is not None and hasattr(tx, k):
            if k == "direction":
                setattr(tx, k, FinanceDirection(v))
            elif k == "amount_cents":
                tx.amount_cents = abs(v)
            else:
                setattr(tx, k, v)
    await db.flush()
    await _rebuild_snapshot(db, workspace_id, old_date)
    if tx.occurred_on != old_date:
        await _rebuild_snapshot(db, workspace_id, tx.occurred_on)
    await db.commit()
    return _tx_out(tx)


async def delete_transaction(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    tx_id: uuid.UUID,
) -> dict:
    res = await db.execute(
        select(FinanceTransaction).where(
            FinanceTransaction.id == tx_id,
            FinanceTransaction.workspace_id == workspace_id,
        )
    )
    tx = res.scalar_one_or_none()
    if not tx:
        raise ValueError(f"Transaction {tx_id} not found")
    d = _tx_out(tx)
    old_date = tx.occurred_on
    await db.delete(tx)
    await db.flush()
    await _rebuild_snapshot(db, workspace_id, old_date)
    await db.commit()
    return d


# ── Invoices ──────────────────────────────────────────────────────────────────

def _inv_out(inv: FinanceInvoice) -> dict:
    today = date.today()
    overdue = (
        inv.status in (FinanceInvoiceStatus.draft, FinanceInvoiceStatus.sent)
        and inv.due_on is not None
        and inv.due_on < today
    )
    return {
        "id": str(inv.id),
        "workspace_id": str(inv.workspace_id),
        "customer_name": inv.customer_name,
        "amount_cents": inv.amount_cents,
        "currency": inv.currency,
        "issued_on": inv.issued_on.isoformat() if inv.issued_on else None,
        "due_on": inv.due_on.isoformat() if inv.due_on else None,
        "status": inv.status.value,
        "paid_on": inv.paid_on.isoformat() if inv.paid_on else None,
        "notes": inv.notes,
        "linked_transaction_id": str(inv.linked_transaction_id) if inv.linked_transaction_id else None,
        "overdue": overdue,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }


async def list_invoices(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    status: Optional[str] = None,
) -> list[dict]:
    q = select(FinanceInvoice).where(FinanceInvoice.workspace_id == workspace_id)
    if status:
        q = q.where(FinanceInvoice.status == FinanceInvoiceStatus(status))
    q = q.order_by(FinanceInvoice.due_on.asc().nullslast(), FinanceInvoice.created_at.desc())
    res = await db.execute(q)
    return [_inv_out(inv) for inv in res.scalars().all()]


async def create_invoice(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    customer_name: str,
    amount_cents: int,
    currency: str = "INR",
    issued_on: Optional[date] = None,
    due_on: Optional[date] = None,
    notes: Optional[str] = None,
    created_by: Optional[uuid.UUID] = None,
) -> dict:
    inv = FinanceInvoice(
        workspace_id=workspace_id,
        customer_name=customer_name,
        amount_cents=abs(amount_cents),
        currency=currency,
        issued_on=issued_on or date.today(),
        due_on=due_on,
        notes=notes,
        status=FinanceInvoiceStatus.draft,
        created_by=created_by,
    )
    db.add(inv)
    await db.flush()
    await db.commit()
    return _inv_out(inv)


async def update_invoice(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    invoice_id: uuid.UUID,
    **kwargs,
) -> dict:
    res = await db.execute(
        select(FinanceInvoice).where(
            FinanceInvoice.id == invoice_id,
            FinanceInvoice.workspace_id == workspace_id,
        )
    )
    inv = res.scalar_one_or_none()
    if not inv:
        raise ValueError(f"Invoice {invoice_id} not found")
    for k, v in kwargs.items():
        if v is not None and hasattr(inv, k):
            if k == "status":
                inv.status = FinanceInvoiceStatus(v)
            else:
                setattr(inv, k, v)
    # Auto-set paid_on when marked paid
    if inv.status == FinanceInvoiceStatus.paid and not inv.paid_on:
        inv.paid_on = date.today()
    await db.commit()
    return _inv_out(inv)


async def mark_invoice_paid(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    invoice_id: uuid.UUID,
    paid_on: Optional[date] = None,
    account_id: Optional[uuid.UUID] = None,
    created_by: Optional[uuid.UUID] = None,
) -> dict:
    """Mark invoice paid and optionally auto-create linked income transaction."""
    res = await db.execute(
        select(FinanceInvoice).where(
            FinanceInvoice.id == invoice_id,
            FinanceInvoice.workspace_id == workspace_id,
        )
    )
    inv = res.scalar_one_or_none()
    if not inv:
        raise ValueError(f"Invoice {invoice_id} not found")

    inv.status = FinanceInvoiceStatus.paid
    inv.paid_on = paid_on or date.today()

    # Auto-link income transaction if account provided
    if account_id and not inv.linked_transaction_id:
        tx = FinanceTransaction(
            workspace_id=workspace_id,
            account_id=account_id,
            direction=FinanceDirection.income,
            amount_cents=inv.amount_cents,
            currency=inv.currency,
            occurred_on=inv.paid_on,
            description=f"Invoice payment — {inv.customer_name}",
            source=FinanceTransactionSource.manual,
            created_by=created_by,
        )
        db.add(tx)
        await db.flush()
        inv.linked_transaction_id = tx.id
        await _rebuild_snapshot(db, workspace_id, inv.paid_on)

    await db.commit()
    return _inv_out(inv)


# ── Summary + overview ────────────────────────────────────────────────────────

async def get_summary(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    period: Optional[str] = None,  # YYYY-MM or None for MTD
) -> dict:
    """Revenue/expense/net for a month or MTD."""
    today = date.today()
    if period:
        y, m = int(period[:4]), int(period[5:7])
        from_date = date(y, m, 1)
        import calendar as _cal
        last_day = _cal.monthrange(y, m)[1]
        to_date = date(y, m, last_day)
        label = period
    else:
        from_date = today.replace(day=1)
        to_date = today
        label = "mtd"

    res = await db.execute(
        select(
            FinanceTransaction.direction,
            func.sum(FinanceTransaction.amount_cents),
        ).where(
            FinanceTransaction.workspace_id == workspace_id,
            FinanceTransaction.occurred_on >= from_date,
            FinanceTransaction.occurred_on <= to_date,
        ).group_by(FinanceTransaction.direction)
    )
    rows = {r[0]: r[1] for r in res.all()}
    revenue = int(rows.get(FinanceDirection.income, 0) or 0)
    expense = int(rows.get(FinanceDirection.expense, 0) or 0)
    return {
        "period": label,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "revenue_cents": revenue,
        "expense_cents": expense,
        "net_cents": revenue - expense,
    }


async def get_cash_position(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    """Sum of balances for cash + bank accounts."""
    res = await db.execute(
        select(FinanceAccount).where(
            FinanceAccount.workspace_id == workspace_id,
            FinanceAccount.is_active == True,  # noqa: E712
            FinanceAccount.type.in_([FinanceAccountType.cash, FinanceAccountType.bank]),
        )
    )
    accounts = res.scalars().all()
    total = 0
    for acc in accounts:
        total += await _account_balance(db, acc)
    return total


async def get_overview(db: AsyncSession, workspace_id: uuid.UUID) -> dict:
    """Dashboard overview: cash, MTD, unpaid invoices."""
    await ensure_finance_setup(db, workspace_id)
    cash = await get_cash_position(db, workspace_id)
    mtd = await get_summary(db, workspace_id)

    # Unpaid invoices
    res = await db.execute(
        select(
            func.count(FinanceInvoice.id),
            func.coalesce(func.sum(FinanceInvoice.amount_cents), 0),
        ).where(
            FinanceInvoice.workspace_id == workspace_id,
            FinanceInvoice.status.in_([FinanceInvoiceStatus.draft, FinanceInvoiceStatus.sent]),
        )
    )
    row = res.one()
    unpaid_count = int(row[0] or 0)
    unpaid_cents = int(row[1] or 0)

    return {
        "cash_position_cents": cash,
        "mtd_revenue_cents": mtd["revenue_cents"],
        "mtd_expense_cents": mtd["expense_cents"],
        "mtd_net_cents": mtd["net_cents"],
        "unpaid_invoices_count": unpaid_count,
        "unpaid_invoices_total_cents": unpaid_cents,
    }


async def list_unpaid_invoices(db: AsyncSession, workspace_id: uuid.UUID) -> list[dict]:
    q = select(FinanceInvoice).where(
        FinanceInvoice.workspace_id == workspace_id,
        FinanceInvoice.status.in_([FinanceInvoiceStatus.draft, FinanceInvoiceStatus.sent]),
    ).order_by(FinanceInvoice.due_on.asc().nullslast())
    res = await db.execute(q)
    return [_inv_out(inv) for inv in res.scalars().all()]


# ── Snapshots (internal) ──────────────────────────────────────────────────────

async def _rebuild_snapshot(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    for_date: date,
) -> None:
    """Recompute monthly snapshot for the month containing for_date."""
    period = for_date.strftime("%Y-%m")
    y, m = int(period[:4]), int(period[5:7])
    import calendar as _cal
    from_date = date(y, m, 1)
    to_date = date(y, m, _cal.monthrange(y, m)[1])

    res = await db.execute(
        select(
            FinanceTransaction.direction,
            func.sum(FinanceTransaction.amount_cents),
        ).where(
            FinanceTransaction.workspace_id == workspace_id,
            FinanceTransaction.occurred_on >= from_date,
            FinanceTransaction.occurred_on <= to_date,
        ).group_by(FinanceTransaction.direction)
    )
    rows = {r[0]: int(r[1] or 0) for r in res.all()}
    revenue = rows.get(FinanceDirection.income, 0)
    expense = rows.get(FinanceDirection.expense, 0)

    snap_res = await db.execute(
        select(FinanceSnapshot).where(
            FinanceSnapshot.workspace_id == workspace_id,
            FinanceSnapshot.period == period,
        )
    )
    snap = snap_res.scalar_one_or_none()
    if snap:
        snap.revenue_cents = revenue
        snap.expense_cents = expense
    else:
        db.add(FinanceSnapshot(
            workspace_id=workspace_id,
            period=period,
            revenue_cents=revenue,
            expense_cents=expense,
        ))


# ── CSV import ────────────────────────────────────────────────────────────────

_COLUMN_ALIASES = {
    "date": "date", "occurred_on": "date", "transaction_date": "date",
    "description": "description", "desc": "description", "narration": "description",
    "amount": "amount", "debit": "amount", "credit": "amount",
    "type": "type", "direction": "type", "kind": "type",
    "category": "category", "category_name": "category",
    "account": "account", "account_name": "account",
}


async def import_csv(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    csv_content: str,
    created_by: Optional[uuid.UUID] = None,
) -> dict:
    """
    Import transactions from CSV. Returns {imported, skipped, errors}.
    Expected columns (flexible): date, description, amount, type (income/expense), category, account
    """
    await ensure_finance_setup(db, workspace_id)

    # Load accounts + categories for lookup
    acc_res = await db.execute(
        select(FinanceAccount).where(FinanceAccount.workspace_id == workspace_id)
    )
    accounts = {a.name.lower(): a for a in acc_res.scalars().all()}

    cat_res = await db.execute(
        select(FinanceCategory).where(FinanceCategory.workspace_id == workspace_id)
    )
    categories = {c.name.lower(): c for c in cat_res.scalars().all()}

    # Fallback categories
    other_income = categories.get("other income")
    other_expense = categories.get("other expense")

    reader = csv.DictReader(io.StringIO(csv_content))
    imported = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):  # row 1 = header
        try:
            # Normalize column names
            norm = {}
            for k, v in row.items():
                mapped = _COLUMN_ALIASES.get((k or "").strip().lower())
                if mapped:
                    norm[mapped] = (v or "").strip()

            if not norm.get("date") or not norm.get("amount"):
                skipped += 1
                continue

            # Parse date
            raw_date = norm["date"]
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    occurred = datetime.strptime(raw_date, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                errors.append(f"Row {i}: cannot parse date '{raw_date}'")
                skipped += 1
                continue

            # Parse amount
            raw_amount = norm["amount"].replace(",", "").replace("₹", "").replace("$", "").strip()
            try:
                amount_float = float(raw_amount)
            except ValueError:
                errors.append(f"Row {i}: cannot parse amount '{norm['amount']}'")
                skipped += 1
                continue
            amount_cents = int(abs(amount_float) * 100)

            # Direction
            direction_raw = (norm.get("type") or "").lower()
            if direction_raw in ("income", "credit", "cr", "+"):
                direction = FinanceDirection.income
            elif direction_raw in ("expense", "debit", "dr", "-"):
                direction = FinanceDirection.expense
            elif amount_float < 0:
                direction = FinanceDirection.expense
            else:
                direction = FinanceDirection.income

            # Account
            acc_name = (norm.get("account") or "").lower()
            account = accounts.get(acc_name)
            if not account:
                # use first active account as fallback if only one
                active = [a for a in accounts.values() if a.is_active]
                if len(active) == 1:
                    account = active[0]
                else:
                    errors.append(f"Row {i}: unknown account '{norm.get('account', '')}' — skipped")
                    skipped += 1
                    continue

            # Category
            cat_name = (norm.get("category") or "").lower()
            category = categories.get(cat_name)
            if not category:
                category = other_income if direction == FinanceDirection.income else other_expense

            tx = FinanceTransaction(
                workspace_id=workspace_id,
                account_id=account.id,
                category_id=category.id if category else None,
                direction=direction,
                amount_cents=amount_cents,
                currency="INR",
                occurred_on=occurred,
                description=norm.get("description", "")[:500],
                source=FinanceTransactionSource.import_,
                created_by=created_by,
            )
            db.add(tx)
            imported += 1

        except Exception as e:
            errors.append(f"Row {i}: {str(e)[:100]}")
            skipped += 1

    if imported > 0:
        await db.commit()

    return {"imported": imported, "skipped": skipped, "errors": errors[:50]}
