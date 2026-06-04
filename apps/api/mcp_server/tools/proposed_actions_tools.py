"""
MCP tools to list / approve / reject proposed actions (for Telegram and in-app agent flows).
"""
import uuid
from typing import Optional

from sqlalchemy import select

from db.session import AsyncSessionLocal
from mcp_server.helpers import get_workspace_actor_id
from mcp_server.server import mcp, agent_broadcast
from models.agent import ProposedAction
from core.proposed_action_exec import execute_proposed_action, reject_proposed_action
from fastapi import HTTPException


def _action_summary(a: ProposedAction) -> dict:
    return {
        "id": str(a.id),
        "action_type": a.action_type,
        "status": a.status,
        "risk_level": a.risk_level,
        "payload": a.payload,
        "proposed_at": a.proposed_at.isoformat() if a.proposed_at else None,
    }


@mcp.tool()
async def lno_list_proposed_actions(
    workspace_id: str,
    status: str = "pending",
) -> list[dict]:
    """
    List proposed actions awaiting human approval (or filter by status).
    Use before approve/reject so you have the correct action_id.
    """
    async with AsyncSessionLocal() as db:
        q = select(ProposedAction).where(
            ProposedAction.workspace_id == uuid.UUID(workspace_id)
        )
        if status and status != "all":
            q = q.where(ProposedAction.status == status)
        q = q.order_by(ProposedAction.proposed_at.desc()).limit(50)
        result = await db.execute(q)
        actions = result.scalars().all()
    await agent_broadcast(workspace_id, "lno_list_proposed_actions", "done", f"{len(actions)} actions")
    return [_action_summary(a) for a in actions]


@mcp.tool()
async def lno_approve_proposed_action(
    workspace_id: str,
    action_id: str,
) -> dict:
    """
    Approve and execute a pending proposed action (e.g. gmail_send sends the email).
    Use when the user says approve in Telegram or in chat.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProposedAction).where(
                ProposedAction.id == uuid.UUID(action_id),
                ProposedAction.workspace_id == uuid.UUID(workspace_id),
            )
        )
        action = result.scalar_one_or_none()
        if not action:
            return {"error": "Proposed action not found"}
        actor_id = await get_workspace_actor_id(uuid.UUID(workspace_id))
        action_type = action.action_type
        try:
            execution_result = await execute_proposed_action(
                action,
                db,
                workspace_id=workspace_id,
                actor_user_id=actor_id,
            )
        except HTTPException as e:
            return {"error": e.detail, "status_code": e.status_code}
        except Exception as e:
            action.status = "failed"
            action.execution_result = {"error": str(e)}
            await db.commit()
            return {"error": str(e)}

    await agent_broadcast(
        workspace_id,
        "lno_approve_proposed_action",
        "done",
        f"Executed {action_type}",
    )
    return {
        "ok": True,
        "executed": True,
        "action_type": action_type,
        "result": execution_result,
    }


@mcp.tool()
async def lno_reject_proposed_action(
    workspace_id: str,
    action_id: str,
) -> dict:
    """Reject a pending proposed action without executing it."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ProposedAction).where(
                ProposedAction.id == uuid.UUID(action_id),
                ProposedAction.workspace_id == uuid.UUID(workspace_id),
            )
        )
        action = result.scalar_one_or_none()
        if not action:
            return {"error": "Proposed action not found"}
        actor_id = await get_workspace_actor_id(uuid.UUID(workspace_id))
        try:
            await reject_proposed_action(action, db, actor_user_id=actor_id)
        except HTTPException as e:
            return {"error": e.detail}

    await agent_broadcast(workspace_id, "lno_reject_proposed_action", "done", action_id[:8])
    return {"ok": True, "rejected": True, "action_id": action_id}
