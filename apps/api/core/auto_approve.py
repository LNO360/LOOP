"""Background auto-approver for low/medium-risk proposed actions.

When enabled, pending proposed actions whose risk_level is "low" or "medium"
(create/update tasks & projects, channel messages, calendar, gmail send, github,
etc.) are executed automatically without human approval. High-risk actions
(deletes — e.g. finance_delete_transaction, delete task/project/message) are
intentionally NOT auto-approved and stay pending for a human.

Runs on an APScheduler interval. The api runs multiple uvicorn workers, so each
worker has its own scheduler; every pending action is therefore claimed with
SELECT ... FOR UPDATE SKIP LOCKED and the row lock is held through execution +
commit, guaranteeing each action is executed exactly once across all workers.
"""
import logging

from fastapi import HTTPException
from sqlalchemy import select, update

from core.config import settings
from core.proposed_action_exec import execute_proposed_action
from db.session import AsyncSessionLocal
from mcp_server.helpers import get_workspace_actor_id
from models.agent import ProposedAction

logger = logging.getLogger("auto_approve")

# Risk levels eligible for auto-approval. "high" (destructive deletes) is excluded
# by design — those always require human approval.
AUTO_APPROVE_RISK_LEVELS = ("low", "medium")


async def auto_approve_pending_actions(max_per_run: int = 50) -> int:
    """Execute pending low/medium-risk proposed actions without human approval.

    Returns the number of actions executed this run. Safe to run concurrently in
    multiple workers: each action is claimed via FOR UPDATE SKIP LOCKED, so two
    workers never execute the same action.
    """
    if not settings.auto_approve_enabled:
        return 0

    executed = 0
    for _ in range(max_per_run):
        async with AsyncSessionLocal() as db:
            row = await db.execute(
                select(ProposedAction)
                .where(
                    ProposedAction.status == "pending",
                    ProposedAction.risk_level.in_(AUTO_APPROVE_RISK_LEVELS),
                    # Defense-in-depth: never auto-approve a destructive delete,
                    # even if some call site mistags its risk_level below "high".
                    ~ProposedAction.action_type.ilike("%delete%"),
                )
                .order_by(ProposedAction.proposed_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            action = row.scalar_one_or_none()
            if action is None:
                break  # nothing left to auto-approve this run

            action_id = action.id
            ws_id = str(action.workspace_id)
            action_type = action.action_type
            try:
                actor_id = await get_workspace_actor_id(action.workspace_id)
                # execute_proposed_action sets status="executed" and commits.
                await execute_proposed_action(
                    action,
                    db,
                    workspace_id=ws_id,
                    actor_user_id=actor_id,
                )
                executed += 1
                logger.info("auto-approved %s (%s) ws=%s", action_id, action_type, ws_id)
            except Exception as e:  # noqa: BLE001 — one bad action must not stop the sweep
                # The failed flush leaves this session needing a rollback, so we
                # can't mark the action failed on it — do that in a fresh session
                # (and release the row lock) to avoid an infinite retry loop.
                detail = e.detail if isinstance(e, HTTPException) else str(e)
                await db.rollback()
                await _mark_failed(action_id, detail)
                logger.warning(
                    "auto-approve failed %s (%s): %s", action_id, action_type, detail
                )

    return executed


async def _mark_failed(action_id, detail: str) -> None:
    """Mark a proposed action failed in its own transaction (after a rollback)."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ProposedAction)
            .where(ProposedAction.id == action_id)
            .values(
                status="failed",
                execution_result={"error": detail, "auto_approve": True},
            )
        )
        await db.commit()
