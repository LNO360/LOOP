"""
Finance MCP tools (workspace-level, manual ledger).

Read (immediate):
  finance_get_overview          — cash + MTD + unpaid invoices
  finance_get_summary           — revenue/expense/net for period
  finance_list_accounts         — accounts + computed balances
  finance_list_transactions     — filtered ledger
  finance_list_unpaid_invoices  — AR overdue + due soon
  finance_list_categories       — for categorization help

Write (proposed_action):
  finance_create_transaction    — medium risk
  finance_update_transaction    — medium risk
  finance_delete_transaction    — high risk
  finance_create_invoice        — low risk
  finance_mark_invoice_paid     — medium risk
"""
import uuid
from datetime import date
from typing import Optional

from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
import services.finance_service as fs


# ── Read tools ────────────────────────────────────────────────────────────────

@mcp.tool()
async def finance_get_overview(workspace_id: str) -> dict:
    """
    Get workspace finance overview: cash position, MTD revenue/expense/net, unpaid invoices.
    Returns {cash_position_cents, mtd_revenue_cents, mtd_expense_cents, mtd_net_cents,
             unpaid_invoices_count, unpaid_invoices_total_cents}.
    All amounts in smallest currency unit (paise for INR, cents for USD, etc.).
    """
    async with AsyncSessionLocal() as db:
        return await fs.get_overview(db, uuid.UUID(workspace_id))


@mcp.tool()
async def finance_get_summary(
    workspace_id: str,
    period: Optional[str] = None,
) -> dict:
    """
    Get revenue/expense/net for a period.
    period: 'YYYY-MM' for a specific month, or omit for current month-to-date.
    Returns {period, from_date, to_date, revenue_cents, expense_cents, net_cents}.
    """
    async with AsyncSessionLocal() as db:
        return await fs.get_summary(db, uuid.UUID(workspace_id), period=period)


@mcp.tool()
async def finance_list_accounts(workspace_id: str) -> list[dict]:
    """
    List all finance accounts (cash, bank, other) with current computed balances.
    Returns [{id, name, type, balance_cents, is_active, opening_balance_cents}].
    """
    async with AsyncSessionLocal() as db:
        await agent_broadcast(workspace_id, "finance_list_accounts", "running")
        result = await fs.list_accounts(db, uuid.UUID(workspace_id))
        await agent_broadcast(workspace_id, "finance_list_accounts", "done", f"{len(result)} accounts")
        return result


@mcp.tool()
async def finance_list_transactions(
    workspace_id: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    direction: Optional[str] = None,
    category_id: Optional[str] = None,
    account_id: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    List finance transactions with optional filters.
    from_date / to_date: ISO date strings (YYYY-MM-DD).
    direction: 'income' | 'expense'.
    Returns [{id, direction, amount_cents, currency, occurred_on, description, category_id, account_id}].
    """
    async with AsyncSessionLocal() as db:
        await agent_broadcast(workspace_id, "finance_list_transactions", "running")
        result = await fs.list_transactions(
            db,
            uuid.UUID(workspace_id),
            from_date=date.fromisoformat(from_date) if from_date else None,
            to_date=date.fromisoformat(to_date) if to_date else None,
            direction=direction,
            category_id=uuid.UUID(category_id) if category_id else None,
            account_id=uuid.UUID(account_id) if account_id else None,
            limit=min(limit, 200),
        )
        await agent_broadcast(workspace_id, "finance_list_transactions", "done", f"{len(result)} rows")
        return result


@mcp.tool()
async def finance_list_unpaid_invoices(workspace_id: str) -> list[dict]:
    """
    List unpaid invoices (draft + sent). Includes overdue flag.
    Returns [{id, customer_name, amount_cents, currency, due_on, status, overdue}].
    """
    async with AsyncSessionLocal() as db:
        result = await fs.list_unpaid_invoices(db, uuid.UUID(workspace_id))
        await agent_broadcast(workspace_id, "finance_list_unpaid_invoices", "done", f"{len(result)} unpaid")
        return result


@mcp.tool()
async def finance_list_categories(workspace_id: str) -> list[dict]:
    """
    List all finance categories (income + expense, system + custom).
    Returns [{id, name, kind, is_system, sort_order}].
    """
    async with AsyncSessionLocal() as db:
        return await fs.list_categories(db, uuid.UUID(workspace_id))


# ── Write tools (proposed_actions) ───────────────────────────────────────────

def _proposed(action_id: str, action_type: str, msg: str) -> dict:
    return {"proposed": True, "action_id": action_id, "message": msg}


@mcp.tool()
async def finance_create_transaction(
    workspace_id: str,
    account_id: str,
    direction: str,
    amount_cents: int,
    occurred_on: str,
    description: str,
    currency: str = "INR",
    category_id: Optional[str] = None,
    reference: Optional[str] = None,
) -> dict:
    """
    Propose creating a finance transaction. Requires human approval.
    direction: 'income' | 'expense'.
    amount_cents: positive integer in smallest currency unit.
    occurred_on: ISO date string e.g. '2026-05-01'.
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="finance_create_transaction",
            payload={
                "account_id": account_id,
                "direction": direction,
                "amount_cents": amount_cents,
                "occurred_on": occurred_on,
                "description": description,
                "currency": currency,
                "category_id": category_id,
                "reference": reference,
            },
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="finance_create_transaction",
            payload={
                "direction": direction,
                "amount_cents": amount_cents,
                "currency": currency,
                "description": description,
                "occurred_on": occurred_on,
            },
        )

    await agent_broadcast(workspace_id, "finance_create_transaction", "done", f"Proposed: {direction} {amount_cents/100:.2f}")
    return _proposed(action_id, "finance_create_transaction",
                     f"Transaction '{description}' queued for approval in AI Work → Actions.")


@mcp.tool()
async def finance_update_transaction(
    workspace_id: str,
    transaction_id: str,
    direction: Optional[str] = None,
    amount_cents: Optional[int] = None,
    occurred_on: Optional[str] = None,
    description: Optional[str] = None,
    category_id: Optional[str] = None,
    reference: Optional[str] = None,
) -> dict:
    """
    Propose updating a finance transaction. Requires human approval.
    Only provided fields are updated.
    """
    from models.agent import ProposedAction
    patch = {k: v for k, v in {
        "direction": direction, "amount_cents": amount_cents,
        "occurred_on": occurred_on, "description": description,
        "category_id": category_id, "reference": reference,
    }.items() if v is not None}

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="finance_update_transaction",
            payload={"transaction_id": transaction_id, "patch": patch},
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="finance_update_transaction",
            payload={"transaction_id": transaction_id, "fields": list(patch.keys())},
        )

    await agent_broadcast(workspace_id, "finance_update_transaction", "done", f"Proposed: update {transaction_id[:8]}")
    return _proposed(action_id, "finance_update_transaction",
                     f"Update transaction '{transaction_id[:8]}…' queued for approval.")


@mcp.tool()
async def finance_delete_transaction(
    workspace_id: str,
    transaction_id: str,
) -> dict:
    """
    Propose deleting a finance transaction. HIGH risk — requires human approval.
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="finance_delete_transaction",
            payload={"transaction_id": transaction_id},
            risk_level="high",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="finance_delete_transaction",
            payload={"transaction_id": transaction_id},
        )

    await agent_broadcast(workspace_id, "finance_delete_transaction", "done", f"Proposed: DELETE {transaction_id[:8]}")
    return _proposed(action_id, "finance_delete_transaction",
                     f"Delete transaction '{transaction_id[:8]}…' queued for approval. ⚠️ Permanent.")


@mcp.tool()
async def finance_create_invoice(
    workspace_id: str,
    customer_name: str,
    amount_cents: int,
    currency: str = "INR",
    issued_on: Optional[str] = None,
    due_on: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """
    Propose creating an invoice (accounts receivable). Low risk — requires human approval.
    amount_cents: invoice total in smallest currency unit.
    due_on: ISO date string YYYY-MM-DD.
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="finance_create_invoice",
            payload={
                "customer_name": customer_name,
                "amount_cents": amount_cents,
                "currency": currency,
                "issued_on": issued_on,
                "due_on": due_on,
                "notes": notes,
            },
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="finance_create_invoice",
            payload={
                "customer_name": customer_name,
                "amount_cents": amount_cents,
                "currency": currency,
                "due_on": due_on,
            },
        )

    await agent_broadcast(workspace_id, "finance_create_invoice", "done", f"Proposed: invoice for {customer_name}")
    return _proposed(action_id, "finance_create_invoice",
                     f"Invoice for '{customer_name}' ({amount_cents/100:.2f} {currency}) queued for approval.")


@mcp.tool()
async def finance_mark_invoice_paid(
    workspace_id: str,
    invoice_id: str,
    paid_on: Optional[str] = None,
    account_id: Optional[str] = None,
) -> dict:
    """
    Propose marking an invoice as paid. Medium risk — requires human approval.
    account_id: optional — if provided, auto-creates an income transaction on approval.
    paid_on: ISO date string; defaults to today on execution.
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="finance_mark_invoice_paid",
            payload={
                "invoice_id": invoice_id,
                "paid_on": paid_on,
                "account_id": account_id,
            },
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="finance_mark_invoice_paid",
            payload={"invoice_id": invoice_id, "paid_on": paid_on},
        )

    await agent_broadcast(workspace_id, "finance_mark_invoice_paid", "done", f"Proposed: mark {invoice_id[:8]} paid")
    return _proposed(action_id, "finance_mark_invoice_paid",
                     f"Mark invoice '{invoice_id[:8]}…' paid queued for approval.")
