"""
Hermes direct-chat and user-agent management.

Routes:
  POST  /workspaces/{id}/hermes/chat              — SSE stream: chat directly with Hermes
  GET   /workspaces/{id}/hermes/agents            — list user-created agents + built-in agents
  POST  /workspaces/{id}/hermes/agents            — create a new custom agent
  GET   /workspaces/{id}/hermes/agents/{agent_id} — get agent details
  PUT   /workspaces/{id}/hermes/agents/{agent_id} — update agent (name/soul/schedule/model)
  DELETE /workspaces/{id}/hermes/agents/{agent_id}— delete agent + deregister cron
  POST  /workspaces/{id}/hermes/agents/{agent_id}/run — trigger agent run now

Hermes chat uses `docker exec lnoos-hermes-1 hermes chat -q "..."` and streams
stdout back as Server-Sent Events. This gives the user a live terminal-like
experience with Hermes's full MCP toolset.
"""
import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.chat_compression import compress_and_extract
from core.hermes_actions import (
    docker_exec as _docker_exec,
    register_agent_cron as _register_cron,
    remove_agent_cron as _remove_cron,
    HERMES_CONTAINER,
)
from db.session import get_db
from models.agent import UserAgent, AgentRun
from models.ai_chat import HermesChatSession
from models.workspace import Workspace

router = APIRouter(prefix="/api/v1/workspaces/{workspace_id}", tags=["hermes"])

logger = logging.getLogger("hermes_chat")

# Volume path where user-agent skill files are written
# Matches the docker-compose volume: ./apps/user-agent-skills:/user-agent-skills
SKILL_DIR = Path(__file__).parent.parent.parent / "user-agent-skills"

# ── Hermes config file paths (host-side, accessed by FastAPI directly) ────────
# These files are bind-mounted into the Hermes container so edits take effect
# without restarting the container.
_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # → LNO OS/
SOUL_MD_PATH   = _REPO_ROOT / "hermes/SOUL.md"
CONFIG_YAML_PATH = _REPO_ROOT / "hermes/config.yaml"
MEMORY_MD_PATH = _REPO_ROOT / "apps/hermes-data/memories/MEMORY.md"
USER_MD_PATH   = _REPO_ROOT / "apps/hermes-data/memories/USER.md"


def _read_host_file(path: Path) -> str:
    """Read a host-side Hermes file. Creates it empty if missing."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    return path.read_text()


def _write_host_file(path: Path, content: str) -> None:
    """Write a host-side Hermes file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


async def _load_session(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    agent_slug: str | None,
) -> HermesChatSession | None:
    result = await db.execute(
        select(HermesChatSession).where(
            HermesChatSession.workspace_id == workspace_id,
            HermesChatSession.user_id == user_id,
            HermesChatSession.agent_slug == agent_slug,
        )
    )
    return result.scalar_one_or_none()


def _build_history_prefix(session: HermesChatSession | None) -> str:
    """Format session summary + raw_tail into a [CONVERSATION HISTORY] block."""
    if not session:
        return ""
    parts = []
    if session.summary:
        parts.append(session.summary)
    tail = session.raw_tail or []
    if tail:
        parts.append("\nRecent exchanges:")
        for ex in tail:
            parts.append(f"User: {ex['user']}\nHermes: {ex['hermes']}")
    if not parts:
        return ""
    return "\n[CONVERSATION HISTORY]\n" + "\n".join(parts) + "\n"


_RAW_TAIL_COMPRESS_THRESHOLD = 3000  # chars; triggers compression
_RAW_TAIL_KEEP = 3                   # exchanges to keep verbatim after compression


async def _update_session(
    db: AsyncSession,
    workspace_id: str,
    user_id: str,
    agent_slug: str | None,
    exchange: dict,
) -> None:
    """Append exchange to session raw_tail; compress if over threshold."""
    ws_uuid = uuid.UUID(workspace_id)
    user_uuid = uuid.UUID(user_id)

    result = await db.execute(
        select(HermesChatSession).where(
            HermesChatSession.workspace_id == ws_uuid,
            HermesChatSession.user_id == user_uuid,
            HermesChatSession.agent_slug == agent_slug,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = HermesChatSession(
            workspace_id=ws_uuid,
            user_id=user_uuid,
            agent_slug=agent_slug,
            raw_tail=[exchange],
            message_count=1,
        )
        db.add(row)
        await db.commit()
        return

    tail = list(row.raw_tail or [])
    tail.append(exchange)
    row.message_count = (row.message_count or 0) + 1

    total_chars = sum(len(e.get("user", "")) + len(e.get("hermes", "")) for e in tail)
    if total_chars > _RAW_TAIL_COMPRESS_THRESHOLD:
        to_compress = tail[:-_RAW_TAIL_KEEP] or tail[:1]
        row.summary = await compress_and_extract(
            to_compress, row.summary, str(workspace_id), db
        )
        row.raw_tail = tail[-_RAW_TAIL_KEEP:]
    else:
        row.raw_tail = tail

    await db.commit()


# ── Built-in Hermes agents ────────────────────────────────────────────────────
BUILTIN_AGENTS = [
    {
        "id": "builtin-ops-monitor",
        "name": "Ops Monitor",
        "slug": "ops-monitor",
        "avatar_emoji": "🔍",
        "description": "Scans all workspaces every 2 hours for operational issues",
        "schedule": "every 2 hours",
        "builtin": True,
        "skill": "lno-ops-monitor",
    },
    {
        "id": "builtin-daily-digest",
        "name": "Daily Digest",
        "slug": "daily-digest",
        "avatar_emoji": "📋",
        "description": "Generates a morning digest at 8am UTC",
        "schedule": "0 8 * * *",
        "builtin": True,
        "skill": "lno-daily-digest",
    },
    {
        "id": "builtin-product-manager",
        "name": "Product Manager",
        "slug": "product-manager",
        "avatar_emoji": "📊",
        "description": "Weekly project velocity analysis every Monday 9am UTC",
        "schedule": "0 9 * * 1",
        "builtin": True,
        "skill": "lno-product-manager",
    },
    {
        "id": "builtin-team-pulse",
        "name": "Team Pulse",
        "slug": "team-pulse",
        "avatar_emoji": "💓",
        "description": "Weekly team health check every Friday 4pm UTC",
        "schedule": "0 16 * * 5",
        "builtin": True,
        "skill": "lno-team-pulse",
    },
    {
        "id": "builtin-memory-gardener",
        "name": "Memory Gardener",
        "slug": "memory-gardener",
        "avatar_emoji": "🪴",
        "description": "Weekly memory cleanup — dedupes, merges & prunes workspace memory (Sundays 3am UTC)",
        "schedule": "0 3 * * 0",
        "builtin": True,
        "skill": "lno-memory-gardener",
    },
]


# ── Schemas ───────────────────────────────────────────────────────────────────

class HermesChatRequest(BaseModel):
    message: str
    agent_slug: Optional[str] = None   # load a specific agent's personality
    max_turns: int = 12                # bound the agentic loop (each turn re-reads full context)


class CreateAgentRequest(BaseModel):
    name: str
    avatar_emoji: str = "🤖"
    description: Optional[str] = None
    soul_md: str                        # full personality / instruction markdown
    schedule: Optional[str] = None     # cron or human schedule
    model: Optional[str] = None        # override model
    extra_skills: Optional[str] = None


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    avatar_emoji: Optional[str] = None
    description: Optional[str] = None
    soul_md: Optional[str] = None
    schedule: Optional[str] = None
    model: Optional[str] = None
    extra_skills: Optional[str] = None
    active: Optional[bool] = None


class HermesFileRequest(BaseModel):
    content: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")[:60]


def _skill_path(slug: str) -> Path:
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    return SKILL_DIR / f"{slug}.md"


def _write_skill_file(agent: UserAgent) -> None:
    """Write the agent's soul_md as a Hermes skill file."""
    header = f"---\nname: {agent.name}\nslug: {agent.slug}\n"
    if agent.schedule:
        header += f"SCHEDULE: {agent.schedule}\n"
    if agent.model:
        header += f"MODEL: {agent.model}\n"
    header += "---\n\n"
    _skill_path(agent.slug).write_text(header + agent.soul_md)


def _delete_skill_file(slug: str) -> None:
    p = _skill_path(slug)
    if p.exists():
        p.unlink()


# ── Hermes config file endpoints ──────────────────────────────────────────────

@router.get("/hermes/soul")
async def get_soul_md(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """Read Hermes SOUL.md — core personality and operating instructions."""
    return {"content": _read_host_file(SOUL_MD_PATH)}


@router.put("/hermes/soul")
async def put_soul_md(
    workspace_id: str,
    body: HermesFileRequest,
    current_user=Depends(get_current_user),
):
    """Overwrite Hermes SOUL.md."""
    _write_host_file(SOUL_MD_PATH, body.content)
    return {"ok": True, "chars": len(body.content)}


@router.get("/hermes/memory")
async def get_memory_md(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """Read Hermes MEMORY.md — accumulated workspace knowledge."""
    return {"content": _read_host_file(MEMORY_MD_PATH)}


@router.put("/hermes/memory")
async def put_memory_md(
    workspace_id: str,
    body: HermesFileRequest,
    current_user=Depends(get_current_user),
):
    """Overwrite Hermes MEMORY.md."""
    _write_host_file(MEMORY_MD_PATH, body.content)
    return {"ok": True, "chars": len(body.content)}


@router.get("/hermes/user-profile")
async def get_user_profile(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """Read Hermes USER.md — user profile/preferences known to Hermes."""
    return {"content": _read_host_file(USER_MD_PATH)}


@router.put("/hermes/user-profile")
async def put_user_profile(
    workspace_id: str,
    body: HermesFileRequest,
    current_user=Depends(get_current_user),
):
    """Overwrite Hermes USER.md."""
    _write_host_file(USER_MD_PATH, body.content)
    return {"ok": True, "chars": len(body.content)}


@router.get("/hermes/config")
async def get_hermes_config(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """Read hermes/config.yaml — model, fallbacks, approvals, etc."""
    return {"content": _read_host_file(CONFIG_YAML_PATH)}


@router.put("/hermes/config")
async def put_hermes_config(
    workspace_id: str,
    body: HermesFileRequest,
    current_user=Depends(get_current_user),
):
    """Overwrite hermes/config.yaml. Changes take effect on next Hermes start."""
    _write_host_file(CONFIG_YAML_PATH, body.content)
    return {"ok": True, "chars": len(body.content)}


# ── Clear conversation session ────────────────────────────────────────────────

@router.delete("/hermes/session")
async def clear_hermes_session(
    workspace_id: str,
    agent_slug: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Clear the rolling conversation session for the current user."""
    ws_uuid = uuid.UUID(workspace_id)
    result = await db.execute(
        select(HermesChatSession).where(
            HermesChatSession.workspace_id == ws_uuid,
            HermesChatSession.user_id == current_user.id,
            HermesChatSession.agent_slug == agent_slug,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        await db.delete(row)
        await db.commit()
    return {"ok": True}


# ── Hermes chat (SSE stream) ──────────────────────────────────────────────────

@router.post("/hermes/chat")
async def chat_with_hermes(
    workspace_id: str,
    body: HermesChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Chat directly with Hermes. Streams response as Server-Sent Events.
    Hermes has full access: all MCP tools + file_read/write + skills.

    If agent_slug is provided, loads that agent's skill file for personality.
    """
    hermes_session = await _load_session(
        db, uuid.UUID(workspace_id), current_user.id, body.agent_slug
    )
    history_block = _build_history_prefix(hermes_session)

    # Prepend workspace context so Hermes knows the active workspace immediately.
    # This avoids requiring lno_list_workspaces() on every turn (smaller models skip tools).
    workspace_prefix = (
        f"[CONTEXT] Active workspace_id: {workspace_id}\n"
        f"User: {current_user.email}\n"
        f"Use this workspace_id directly in all MCP tool calls — "
        f"do NOT call lno_list_workspaces first.\n"
        f"{history_block}"
        f"\n[USER MESSAGE]\n{body.message}"
    )

    cmd = [
        "hermes", "chat",
        "-q", workspace_prefix,
        "--max-turns", str(body.max_turns),
        "--yolo",  # auto-approve, Hermes has full access
    ]

    # Load specific agent personality if requested
    if body.agent_slug:
        user_skill = f"user/{body.agent_slug}"
        builtin_skill = f"lno/{body.agent_slug}"
        cmd += ["-s", user_skill if _skill_path(body.agent_slug).exists() else builtin_skill]

    accumulated_response: list[str] = []

    async def event_stream():
        import re as _re
        # Strip ANSI escape codes and carriage returns
        _ansi = _re.compile(r'\x1b\[[0-9;]*[mGKHF]|\x1b\(B|\r')

        # Static chrome lines to always skip
        _chrome = _re.compile(
            r'^(?:'
            r'Initializing agent'
            r'|─{3,}'                   # box borders / dividers
            r'|Session:'
            r'|Duration:'
            r'|Messages:'
            r'|⏳ Retrying'
            r'|⏱️'
            r'|⚠️'
            r'|❌'
            r'|🧾'
            r'|✅ Tool'
            r'|→ Tool'
            r'|hermes --resume'          # session resume artifact
            r'|Resume this session'
            r'|\s*$'                     # blank lines
            r')'
        )

        # Context lines we injected — never show these in responses
        _context_noise = {
            f"[CONTEXT] Active workspace_id: {workspace_id}",
            f"User: {current_user.email}",
            "Use this workspace_id directly in all MCP tool calls "
            "— do NOT call lno_list_workspaces first.",
            "[USER MESSAGE]",
        }

        # Tool call line: "⚡ mcp_lno_o  0.1s" or "⚡ tool_name  1.2s"
        _tool_re = _re.compile(r'^[⚡\s⚡]+(\S+)\s+(\d+\.?\d*s)\s*$')

        # State machine
        in_query_echo = False          # True while Hermes is echoing the prompt back
        in_box = False                 # True while inside a ⚕ response box
        box_lines: list[str] = []
        user_msg_first = body.message.strip().split("\n")[0]

        try:
            proc = await _docker_exec(cmd)
            async for raw in proc.stdout:
                line = _ansi.sub("", raw.decode("utf-8", errors="replace")).rstrip()

                # ── Query echo: Hermes prints "Query: <full prompt>" before response ──
                # We skip everything from "Query:" until we've consumed the user message.
                if line.startswith("Query:"):
                    in_query_echo = True
                    continue

                if in_query_echo:
                    # Hermes echoes the full prompt after "Query:". End echo when the
                    # response phase starts — not only on an exact first-line match (wrapped
                    # or single-line queries often never repeat user_msg_first verbatim).
                    stripped_echo = line.strip()
                    if (
                        stripped_echo == user_msg_first
                        or stripped_echo.startswith("Initializing agent")
                        or "⚕" in line
                    ):
                        in_query_echo = False
                    else:
                        continue  # still inside prompt echo

                # ── Belt-and-suspenders: skip context noise even outside echo state ──
                if line.strip() in _context_noise:
                    continue

                # ── Box detection: ⚕ marks Hermes response box ──────────────────────
                if "⚕" in line:
                    if not in_box:
                        in_box = True
                    else:
                        # Second ⚕ = box end — flush accumulated lines
                        content = "\n".join(l.strip() for l in box_lines if l.strip())
                        if content:
                            accumulated_response.append(content)
                            yield f"data: {json.dumps({'text': content + chr(10), 'done': False})}\n\n"
                        box_lines = []
                        in_box = False
                    continue

                # Standalone dash border (box end without ⚕)
                stripped = line.strip()
                if in_box and stripped and len(stripped) > 5 and set(stripped) <= {'─', '━', '═', ' '}:
                    content = "\n".join(l.strip() for l in box_lines if l.strip())
                    if content:
                        accumulated_response.append(content)
                        yield f"data: {json.dumps({'text': content + chr(10), 'done': False})}\n\n"
                    box_lines = []
                    in_box = False
                    continue

                if in_box:
                    # Don't collect hermes resume artifacts even inside box
                    if not line.strip().startswith("hermes --resume"):
                        box_lines.append(line)
                    continue

                # ── Outside box: skip chrome, stream everything else ─────────────────
                # Use line.strip() so leading whitespace doesn't break the match
                if _chrome.match(line.strip()):
                    continue

                # Detect tool call lines (⚡ name  duration)
                tool_m = _tool_re.match(line.strip())
                if tool_m:
                    yield f"data: {json.dumps({'type': 'tool', 'name': tool_m.group(1), 'duration': tool_m.group(2), 'done': False})}\n\n"
                    continue

                if line.strip():
                    accumulated_response.append(line)
                    yield f"data: {json.dumps({'type': 'text', 'text': line + chr(10), 'done': False})}\n\n"

            await proc.wait()

            if proc.returncode not in (0, None) and not accumulated_response:
                yield f"data: {json.dumps({'error': f'Hermes exited with code {proc.returncode}', 'done': True})}\n\n"

            # Flush any remaining box content (strip hermes resume lines)
            if box_lines:
                clean_lines = [l for l in box_lines if not l.strip().startswith("hermes --resume")]
                content = "\n".join(l.strip() for l in clean_lines if l.strip())
                if content:
                    accumulated_response.append(content)
                    yield f"data: {json.dumps({'type': 'text', 'text': content, 'done': False})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'text': '', 'done': True, 'exit_code': proc.returncode})}\n\n"

            # Session update — runs after stream fully ends
            full_response = "\n".join(accumulated_response).strip()
            if full_response:
                try:
                    from db.session import AsyncSessionLocal
                    async with AsyncSessionLocal() as update_db:
                        await _update_session(
                            update_db,
                            workspace_id,
                            str(current_user.id),
                            body.agent_slug,
                            {"user": body.message, "hermes": full_response},
                        )
                except Exception as e:
                    logger.warning("hermes session update failed: %s", e)

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── List all agents (built-in + user-created) ─────────────────────────────────

@router.get("/hermes/agents")
async def list_agents(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.workspace_id == uuid.UUID(workspace_id))
        .order_by(UserAgent.created_at.asc())
    )
    user_agents = result.scalars().all()

    user_agent_list = [
        {
            "id": str(a.id),
            "name": a.name,
            "slug": a.slug,
            "avatar_emoji": a.avatar_emoji,
            "description": a.description,
            "schedule": a.schedule,
            "model": a.model,
            "active": a.active,
            "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "run_count": a.run_count,
            "builtin": False,
        }
        for a in user_agents
    ]

    return {
        "builtin": BUILTIN_AGENTS,
        "custom": user_agent_list,
    }


# ── Create agent ──────────────────────────────────────────────────────────────

@router.post("/hermes/agents")
async def create_agent(
    workspace_id: str,
    body: CreateAgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    slug = slugify(body.name)

    # Ensure unique slug within workspace
    existing = await db.execute(
        select(UserAgent).where(
            UserAgent.workspace_id == uuid.UUID(workspace_id),
            UserAgent.slug == slug,
        )
    )
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:4]}"

    agent = UserAgent(
        workspace_id=uuid.UUID(workspace_id),
        created_by=current_user.id,
        name=body.name,
        slug=slug,
        avatar_emoji=body.avatar_emoji,
        description=body.description,
        soul_md=body.soul_md,
        schedule=body.schedule,
        model=body.model,
        extra_skills=body.extra_skills,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    # Write skill file to shared volume
    _write_skill_file(agent)

    # Register cron if schedule provided
    if body.schedule:
        try:
            await _register_cron(slug, body.schedule)
        except Exception:
            pass  # Non-fatal — user can trigger manually

    return {"agent": _agent_to_dict(agent)}


# ── Get agent ─────────────────────────────────────────────────────────────────

@router.get("/hermes/agents/{agent_id}")
async def get_agent(
    workspace_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    agent = await _get_agent_or_404(db, workspace_id, agent_id)
    return {"agent": _agent_to_dict(agent, include_soul=True)}


# ── Update agent ──────────────────────────────────────────────────────────────

@router.put("/hermes/agents/{agent_id}")
async def update_agent(
    workspace_id: str,
    agent_id: str,
    body: UpdateAgentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    agent = await _get_agent_or_404(db, workspace_id, agent_id)
    old_schedule = agent.schedule

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(agent, field, val)

    await db.commit()
    await db.refresh(agent)

    # Rewrite skill file
    _write_skill_file(agent)

    # Update cron if schedule changed
    if body.schedule is not None and body.schedule != old_schedule:
        try:
            await _remove_cron(agent.slug)
            if body.schedule:
                await _register_cron(agent.slug, body.schedule)
        except Exception:
            pass

    return {"agent": _agent_to_dict(agent, include_soul=True)}


# ── Delete agent ──────────────────────────────────────────────────────────────

@router.delete("/hermes/agents/{agent_id}")
async def delete_agent(
    workspace_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    agent = await _get_agent_or_404(db, workspace_id, agent_id)
    slug = agent.slug

    await db.delete(agent)
    await db.commit()

    _delete_skill_file(slug)

    try:
        await _remove_cron(slug)
    except Exception:
        pass

    return {"ok": True}


# ── Run agent now ─────────────────────────────────────────────────────────────

@router.post("/hermes/agents/{agent_id}/run")
async def run_agent_now(
    workspace_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Trigger an immediate agent run (non-streaming — fires and returns)."""
    agent = await _get_agent_or_404(db, workspace_id, agent_id)

    # Record the run
    run = AgentRun(
        workspace_id=uuid.UUID(workspace_id),
        trigger_type="manual",
        agent_name=agent.slug,
        status="running",
    )
    db.add(run)
    await db.commit()

    # Fire in background
    asyncio.create_task(_run_agent_bg(agent, run.id, db))

    return {"ok": True, "run_id": str(run.id), "agent": agent.name}


async def _run_agent_bg(agent: UserAgent, run_id: uuid.UUID, db: AsyncSession) -> None:
    """Background task: runs agent and updates run record."""
    import datetime
    from db.session import AsyncSessionLocal

    ws = str(agent.workspace_id)
    preamble = (
        f"[CONTEXT] workspace_id: {ws}\n"
        f"Use this workspace_id directly — do NOT call lno_list_workspaces.\n\n"
    )
    prompt = f"{preamble}Use the user/{agent.slug} skill. Read team.handoff.{agent.slug} if present."
    cmd = [
        "hermes", "chat",
        "-q", prompt,
        "--max-turns", "20",
        "--yolo",
    ]
    try:
        proc = await _docker_exec(cmd)
        stdout, _ = await proc.communicate()
        status = "success" if proc.returncode == 0 else "error"
        summary = stdout.decode("utf-8", errors="replace")[-500:] if stdout else ""
    except Exception as e:
        status = "error"
        summary = str(e)

    async with AsyncSessionLocal() as new_db:
        result = await new_db.execute(select(AgentRun).where(AgentRun.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            run.result_summary = summary
            run.finished_at = datetime.datetime.now(datetime.timezone.utc)
        # Update last_run_at on the agent
        a_result = await new_db.execute(
            select(UserAgent).where(UserAgent.id == agent.id)
        )
        a = a_result.scalar_one_or_none()
        if a:
            a.last_run_at = datetime.datetime.now(datetime.timezone.utc)
            a.run_count = (a.run_count or 0) + 1
        await new_db.commit()


# ── MCP self-modification tools (Hermes reads/writes its own config) ──────────
# These are exposed via the MCP server so Hermes can call them during chat.
# See mcp_server/tools/self_modify.py for the actual MCP tools.


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _get_agent_or_404(db: AsyncSession, workspace_id: str, agent_id: str) -> UserAgent:
    result = await db.execute(
        select(UserAgent).where(
            UserAgent.id == uuid.UUID(agent_id),
            UserAgent.workspace_id == uuid.UUID(workspace_id),
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _agent_to_dict(agent: UserAgent, include_soul: bool = False) -> dict:
    d = {
        "id": str(agent.id),
        "name": agent.name,
        "slug": agent.slug,
        "avatar_emoji": agent.avatar_emoji,
        "description": agent.description,
        "schedule": agent.schedule,
        "model": agent.model,
        "extra_skills": agent.extra_skills,
        "active": agent.active,
        "last_run_at": agent.last_run_at.isoformat() if agent.last_run_at else None,
        "run_count": agent.run_count,
        "builtin": False,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }
    if include_soul:
        d["soul_md"] = agent.soul_md
    return d
