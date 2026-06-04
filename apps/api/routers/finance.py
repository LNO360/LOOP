"""
Finance REST API — manual accounts, categories, transactions, invoices.

Base: /api/v1/workspaces/{workspace_id}/finance
"""
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from db.session import get_db
from models import User, WorkspaceMember, MemberRole
from services import finance_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/finance",
    tags=["finance"],
)


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _require_admin(workspace_id: str, db: AsyncSession, current_user: User) -> None:
    """Raise 403 if user is not an admin of the workspace."""
    res = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == uuid.UUID(workspace_id),
            WorkspaceMember.user_id == current_user.id,
        )
    )
    member = res.scalar_one_or_none()
    if not member or member.role != MemberRole.admin:
        raise HTTPException(403, "Finance writes require workspace admin role")


def _ws(workspace_id: str) -> uuid.UUID:
    return uuid.UUID(workspace_id)


# ── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_finance_settings(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.get_settings(db, _ws(workspace_id))


class UpdateSettingsRequest(BaseModel):
    base_currency: Optional[str] = None
    fiscal_year_start_month: Optional[int] = None


@router.patch("/settings")
async def patch_finance_settings(
    workspace_id: str,
    body: UpdateSettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.update_settings(
        db, _ws(workspace_id),
        base_currency=body.base_currency,
        fiscal_year_start_month=body.fiscal_year_start_month,
    )


# ── Accounts ─────────────────────────────────────────────────────────────────

@router.get("/accounts")
async def list_accounts(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.list_accounts(db, _ws(workspace_id))


class CreateAccountRequest(BaseModel):
    name: str
    type: str = "bank"  # cash | bank | other
    opening_balance_cents: int = 0
    opening_balance_date: Optional[str] = None
    notes: Optional[str] = None


@router.post("/accounts")
async def create_account(
    workspace_id: str,
    body: CreateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.create_account(
        db,
        _ws(workspace_id),
        name=body.name,
        type=body.type,
        opening_balance_cents=body.opening_balance_cents,
        opening_balance_date=date.fromisoformat(body.opening_balance_date) if body.opening_balance_date else None,
        notes=body.notes,
        created_by=current_user.id,
    )


class UpdateAccountRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    opening_balance_cents: Optional[int] = None
    opening_balance_date: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.patch("/accounts/{account_id}")
async def update_account(
    workspace_id: str,
    account_id: str,
    body: UpdateAccountRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    kwargs = body.model_dump(exclude_none=True)
    if "opening_balance_date" in kwargs:
        kwargs["opening_balance_date"] = date.fromisoformat(kwargs["opening_balance_date"])
    return await finance_service.update_account(
        db, _ws(workspace_id), uuid.UUID(account_id), **kwargs
    )


@router.delete("/accounts/{account_id}")
async def deactivate_account(
    workspace_id: str,
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.deactivate_account(db, _ws(workspace_id), uuid.UUID(account_id))


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.list_categories(db, _ws(workspace_id))


class CreateCategoryRequest(BaseModel):
    name: str
    kind: str  # income | expense


@router.post("/categories")
async def create_category(
    workspace_id: str,
    body: CreateCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.create_category(
        db, _ws(workspace_id), name=body.name, kind=body.kind
    )


# ── Transactions ──────────────────────────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(
    workspace_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    category_id: Optional[str] = None,
    account_id: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.list_transactions(
        db,
        _ws(workspace_id),
        from_date=date.fromisoformat(from_date) if from_date else None,
        to_date=date.fromisoformat(to_date) if to_date else None,
        category_id=uuid.UUID(category_id) if category_id else None,
        account_id=uuid.UUID(account_id) if account_id else None,
        direction=direction,
        limit=min(limit, 500),
    )


class CreateTransactionRequest(BaseModel):
    account_id: str
    direction: str  # income | expense
    amount_cents: int
    occurred_on: str  # ISO date
    description: str
    currency: str = "INR"
    category_id: Optional[str] = None
    reference: Optional[str] = None


@router.post("/transactions")
async def create_transaction(
    workspace_id: str,
    body: CreateTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.create_transaction(
        db,
        _ws(workspace_id),
        account_id=uuid.UUID(body.account_id),
        direction=body.direction,
        amount_cents=body.amount_cents,
        occurred_on=date.fromisoformat(body.occurred_on),
        description=body.description,
        currency=body.currency,
        category_id=uuid.UUID(body.category_id) if body.category_id else None,
        reference=body.reference,
        source="manual",
        created_by=current_user.id,
    )


class UpdateTransactionRequest(BaseModel):
    direction: Optional[str] = None
    amount_cents: Optional[int] = None
    occurred_on: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    reference: Optional[str] = None


@router.patch("/transactions/{tx_id}")
async def update_transaction(
    workspace_id: str,
    tx_id: str,
    body: UpdateTransactionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    kwargs = body.model_dump(exclude_none=True)
    if "occurred_on" in kwargs:
        kwargs["occurred_on"] = date.fromisoformat(kwargs["occurred_on"])
    if "category_id" in kwargs:
        kwargs["category_id"] = uuid.UUID(kwargs["category_id"])
    return await finance_service.update_transaction(
        db, _ws(workspace_id), uuid.UUID(tx_id), **kwargs
    )


@router.delete("/transactions/{tx_id}")
async def delete_transaction(
    workspace_id: str,
    tx_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.delete_transaction(db, _ws(workspace_id), uuid.UUID(tx_id))


@router.post("/transactions/import")
async def import_transactions_csv(
    workspace_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    content = (await file.read()).decode("utf-8", errors="replace")
    return await finance_service.import_csv(db, _ws(workspace_id), content, created_by=current_user.id)


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(
    workspace_id: str,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.list_invoices(db, _ws(workspace_id), status=status)


class CreateInvoiceRequest(BaseModel):
    customer_name: str
    amount_cents: int
    currency: str = "INR"
    issued_on: Optional[str] = None
    due_on: Optional[str] = None
    notes: Optional[str] = None


@router.post("/invoices")
async def create_invoice(
    workspace_id: str,
    body: CreateInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)
    return await finance_service.create_invoice(
        db,
        _ws(workspace_id),
        customer_name=body.customer_name,
        amount_cents=body.amount_cents,
        currency=body.currency,
        issued_on=date.fromisoformat(body.issued_on) if body.issued_on else None,
        due_on=date.fromisoformat(body.due_on) if body.due_on else None,
        notes=body.notes,
        created_by=current_user.id,
    )


class UpdateInvoiceRequest(BaseModel):
    customer_name: Optional[str] = None
    amount_cents: Optional[int] = None
    status: Optional[str] = None
    issued_on: Optional[str] = None
    due_on: Optional[str] = None
    paid_on: Optional[str] = None
    notes: Optional[str] = None
    account_id: Optional[str] = None  # for mark-paid auto-transaction


@router.patch("/invoices/{invoice_id}")
async def update_invoice(
    workspace_id: str,
    invoice_id: str,
    body: UpdateInvoiceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _require_admin(workspace_id, db, current_user)

    # If marking paid with account_id → use dedicated path
    if body.status == "paid" and body.account_id:
        return await finance_service.mark_invoice_paid(
            db,
            _ws(workspace_id),
            uuid.UUID(invoice_id),
            paid_on=date.fromisoformat(body.paid_on) if body.paid_on else None,
            account_id=uuid.UUID(body.account_id),
            created_by=current_user.id,
        )

    kwargs = body.model_dump(exclude_none=True, exclude={"account_id"})
    for k in ("issued_on", "due_on", "paid_on"):
        if k in kwargs:
            kwargs[k] = date.fromisoformat(kwargs[k])
    return await finance_service.update_invoice(db, _ws(workspace_id), uuid.UUID(invoice_id), **kwargs)


# ── Summary / Overview ────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(
    workspace_id: str,
    period: Optional[str] = None,  # YYYY-MM or omit for MTD
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.get_summary(db, _ws(workspace_id), period=period)


@router.get("/overview")
async def get_overview(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await finance_service.get_overview(db, _ws(workspace_id))
