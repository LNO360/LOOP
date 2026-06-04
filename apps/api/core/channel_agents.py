"""
Slack-style in-channel agents: when a teammate @mentions an agent in a channel,
the agent posts a real, streaming message into that channel as a participant.

Reuses the ACP engine (core/acp_engine.py). One Hermes session per (channel, agent)
so the agent keeps context across mentions in that channel.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid

from sqlalchemy import select, and_

from core.acp_engine import get_engine
from db.session import AsyncSessionLocal
from models import Message, User
from models.agent import UserAgent
from models.ai_chat import ChannelAgentSession
from models.channel import Channel
from ws.manager import manager, broadcast_channel_agent

logger = logging.getLogger("channel_agents")

# @[Multi Word Name]  or  @single-token
_MENTION_RE = re.compile(r"@\[([^\]]+)\]|@([A-Za-z0-9_-]+)")

# How often (seconds) to flush streaming text to the DB + WS while an agent types.
_FLUSH_INTERVAL = 0.4
# Hard timeout for a channel-agent turn (seconds). Cuts off runaway tool chains.
_TURN_TIMEOUT = 60.0

# Always-available general assistant.
HERMES_NAME = "Hermes"
HERMES_SLUG = "hermes"


def extract_mentions(content: str) -> list[str]:
    """Return the raw mention tokens (names/slugs) found in a message."""
    out: list[str] = []
    for bracketed, bare in _MENTION_RE.findall(content):
        token = (bracketed or bare).strip()
        if token:
            out.append(token)
    return out


async def resolve_mentioned_agents(db, workspace_id: uuid.UUID, content: str) -> list[dict]:
    """
    Map mention tokens → mentionable agents in this workspace.
    Returns [{slug, name, persona}] (persona is None for the general Hermes agent).
    De-duplicated by slug.
    """
    tokens = extract_mentions(content)
    if not tokens:
        return []
    lowered = {t.lower() for t in tokens}

    resolved: dict[str, dict] = {}

    if HERMES_SLUG in lowered or HERMES_NAME.lower() in lowered:
        resolved[HERMES_SLUG] = {"slug": HERMES_SLUG, "name": HERMES_NAME, "persona": None}

    result = await db.execute(
        select(UserAgent).where(UserAgent.workspace_id == workspace_id, UserAgent.active.is_(True))
    )
    for a in result.scalars().all():
        if a.slug.lower() in lowered or a.name.lower() in lowered:
            resolved[a.slug] = {"slug": a.slug, "name": a.name, "persona": a.soul_md}

    return list(resolved.values())


async def _recent_context(db, channel_id: uuid.UUID, limit: int = 12) -> str:
    """Build a '[CHANNEL CONTEXT]' transcript of the last few messages."""
    result = await db.execute(
        select(Message, User.name)
        .outerjoin(User, User.id == Message.author_id)
        .where(and_(Message.channel_id == channel_id, Message.deleted_at.is_(None), Message.thread_id.is_(None)))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(reversed(result.all()))
    lines = []
    for msg, author_name in rows:
        who = author_name if msg.sender_type == "user" else (msg.agent_slug or "agent")
        lines.append(f"{who or 'unknown'}: {msg.content}")
    return "\n".join(lines)


def _build_prompt(workspace_id: str, persona: str | None, context: str, trigger: str) -> str:
    parts = [
        f"[CONTEXT] Active workspace_id: {workspace_id}\n"
        f"Use this workspace_id directly in all MCP tool calls — do NOT call lno_list_workspaces first.\n"
        f"You are replying in a team chat channel. Be concise: 2-4 sentences max. "
        f"Use at most 3 tool calls. Give the final answer directly — no preamble like 'Let me check...'.\n\n"
    ]
    if persona:
        parts.append(f"[AGENT PERSONA]\n{persona}\n\n")
    if context:
        parts.append(f"[CHANNEL CONTEXT]\n{context}\n\n")
    parts.append(f"[NEW MESSAGE — you were mentioned]\n{trigger}")
    return "".join(parts)


async def run_channel_agent(
    workspace_id: str,
    channel_id: str,
    agent: dict,
    trigger_content: str,
) -> None:
    """Background task: stream an agent reply into the channel as an agent-authored message."""
    slug = agent["slug"]
    ws_uuid = uuid.UUID(workspace_id)
    ch_uuid = uuid.UUID(channel_id)
    engine = get_engine()

    await broadcast_channel_agent(workspace_id, "agent.typing", channel_id, slug)

    try:
        async with AsyncSessionLocal() as db:
            context = await _recent_context(db, ch_uuid)

            # Placeholder agent message that we stream into.
            msg = Message(
                channel_id=ch_uuid,
                author_id=None,
                sender_type="agent",
                agent_slug=slug,
                content="",
            )
            db.add(msg)
            await db.commit()
            await db.refresh(msg)
            msg_id = msg.id
            await manager.broadcast(workspace_id, {"type": "message.new", "channel_id": channel_id})

            # Per-(channel, agent) Hermes session for cross-mention memory.
            cas = (await db.execute(
                select(ChannelAgentSession).where(
                    ChannelAgentSession.channel_id == ch_uuid,
                    ChannelAgentSession.agent_slug == slug,
                )
            )).scalar_one_or_none()
            if not cas:
                cas = ChannelAgentSession(channel_id=ch_uuid, agent_slug=slug)
                db.add(cas)
                await db.commit()
                await db.refresh(cas)

            engine_key = f"channel:{channel_id}:{slug}"
            try:
                client = await engine.get_or_create(engine_key, cas.hermes_session_id)
            except Exception as e:
                msg.content = f"⚠️ {agent['name']} is unavailable right now."
                await db.commit()
                await manager.broadcast(workspace_id, {"type": "message.updated", "channel_id": channel_id})
                logger.warning("channel agent engine unavailable: %s", e)
                return

            if not cas.hermes_session_id and client.session_id:
                cas.hermes_session_id = client.session_id
                await db.commit()

            prompt = _build_prompt(workspace_id, agent.get("persona"), context, trigger_content)
            text_acc = ""
            last_flush = 0.0

            async def _flush():
                msg.content = text_acc
                await db.commit()
                await manager.broadcast(workspace_id, {"type": "message.updated", "channel_id": channel_id})

            async def _stream():
                nonlocal text_acc, last_flush
                async for ev in client.prompt(prompt):
                    if ev.type == "text_delta":
                        text_acc += ev.text or ""
                        now = time.monotonic()
                        if now - last_flush >= _FLUSH_INTERVAL:
                            last_flush = now
                            await _flush()
                    elif ev.type == "done":
                        break
                    elif ev.type == "error":
                        break

            try:
                await asyncio.wait_for(_stream(), timeout=_TURN_TIMEOUT)
                msg.content = text_acc or "(no response)"
                await db.commit()
                await manager.broadcast(workspace_id, {"type": "message.updated", "channel_id": channel_id})
            except asyncio.TimeoutError:
                logger.warning("channel agent %s timed out after %ss", slug, _TURN_TIMEOUT)
                msg.content = (text_acc + "\n\n*(response timed out)*") if text_acc else f"⚠️ {agent['name']} took too long."
                await db.commit()
                await manager.broadcast(workspace_id, {"type": "message.updated", "channel_id": channel_id})
            except Exception as e:
                logger.warning("channel agent stream failed: %s", e)
                msg.content = text_acc or f"⚠️ {agent['name']} couldn't complete that."
                await db.commit()
                await manager.broadcast(workspace_id, {"type": "message.updated", "channel_id": channel_id})
    finally:
        await broadcast_channel_agent(workspace_id, "agent.done", channel_id, slug)
