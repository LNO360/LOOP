"""
MCP tools for messaging and notifications.

lno_get_channel_messages  — read, executes immediately
lno_send_channel_message  — write, creates proposed_action
lno_create_notification   — low-risk write, executes immediately
"""
import uuid
from typing import Optional
from sqlalchemy import select, and_
from db.session import AsyncSessionLocal
from models import Message, User, Notification
from models.agent import ProposedAction
from mcp_server.server import mcp, agent_broadcast


@mcp.tool()
async def lno_get_channel_messages(
    workspace_id: str,
    channel_id: str,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch recent messages from a channel. Returns in chronological order, up to `limit`.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message, User.name.label("author_name"))
            .join(User, User.id == Message.author_id)
            .where(
                and_(
                    Message.channel_id == uuid.UUID(channel_id),
                    Message.deleted_at.is_(None),
                )
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        rows = result.all()
        messages_out = [
            {
                "id": str(row.Message.id),
                "content": (row.Message.content or "")[:500],
                "author_name": row.author_name,
                "author_id": str(row.Message.author_id),
                "created_at": row.Message.created_at.isoformat(),
            }
            for row in reversed(rows)
        ]
    await agent_broadcast(workspace_id, "lno_get_channel_messages", "done",
                          f"Read {len(messages_out)} messages from channel {channel_id[:8]}")
    return messages_out


@mcp.tool()
async def lno_send_channel_message(
    workspace_id: str,
    channel_id: str,
    content: str,
    run_id: Optional[str] = None,
) -> dict:
    """
    Propose sending a message to a channel. Creates a pending proposed_action.
    Always requires human approval — messages are visible to all workspace members.
    Returns: {"proposed": true, "action_id": "<uuid>", "message": "..."}
    """
    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            run_id=uuid.UUID(run_id) if run_id else None,
            action_type="send_channel_message",
            payload={
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "content": content,
            },
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        preview = content[:80] + ("…" if len(content) > 80 else "")
        result = {
            "proposed": True,
            "action_id": str(action.id),
            "message": f"Message to channel {channel_id} queued for approval: '{preview}'",
        }
    await agent_broadcast(workspace_id, "lno_send_channel_message", "done",
                          f"Proposed message: '{preview}'")
    return result


@mcp.tool()
async def lno_create_notification(
    workspace_id: str,
    user_id: str,
    message: str,
    entity_type: str = "agent_run",
    entity_id: Optional[str] = None,
) -> dict:
    """
    Create a notification for a specific user. Executes immediately (low risk).
    Use this to alert users about findings without posting a visible channel message.
    Returns: {"ok": true, "notification_id": "<uuid>"}
    """
    async with AsyncSessionLocal() as db:
        notif = Notification(
            user_id=uuid.UUID(user_id),
            type="agent",
            entity_type=entity_type,
            entity_id=uuid.UUID(entity_id) if entity_id else uuid.uuid4(),
            message=message,
        )
        db.add(notif)
        await db.commit()
        result = {"ok": True, "notification_id": str(notif.id)}
    await agent_broadcast(workspace_id, "lno_create_notification", "done",
                          f"Notified user {user_id[:8]}: '{message[:60]}'")
    # Push real-time bell update to frontend
    try:
        from ws.manager import notify_user_ws
        await notify_user_ws(workspace_id, user_id)
    except Exception:
        pass
    return result
