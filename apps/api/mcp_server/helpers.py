"""Shared helpers for MCP tool implementations."""
import uuid
from typing import Optional

from sqlalchemy import select

from db.session import AsyncSessionLocal
from models import WorkspaceMember
from models.agent import ProposedAction


async def get_workspace_actor_id(workspace_id: uuid.UUID) -> Optional[uuid.UUID]:
    """First workspace member's user_id — used as created_by / author for agent writes."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .limit(1)
        )
        return result.scalar_one_or_none()


async def propose_destructive_action(
    workspace_id: str,
    action_type: str,
    payload: dict,
    *,
    risk_level: str = "high",
    run_id: Optional[str] = None,
    summary: str = "",
) -> dict:
    """Queue a destructive write for human approval."""
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            run_id=uuid.UUID(run_id) if run_id else None,
            action_type=action_type,
            payload=payload,
            risk_level=risk_level,
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type=action_type,
            payload=payload,
        )
        return {
            "proposed": True,
            "action_id": action_id,
            "action_type": action_type,
            "message": summary or f"{action_type} queued for human approval (action {action_id}).",
        }
