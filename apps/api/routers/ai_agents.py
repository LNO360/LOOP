from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from db.session import get_db
from models import Task, TaskStatus, User, Message, Document, Channel, ChannelType, ChannelMember, Workspace, WorkspaceMember
from core.auth import get_current_user
from core.config import settings
from agents.task_agent import TaskAgent
from agents.project_manager import ProjectManagerAgent
from agents.docs_agent import DocsAgent
from agents.knowledge_agent import KnowledgeAgent
from agents.memory_agent import MemoryAgent
from agents.memory_store import get_memories, upsert_memories, delete_memory
from core.model_router import models_for_profile, profile_for_agent_type
from pydantic import BaseModel
from typing import Optional
import uuid
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces/{workspace_id}/agents", tags=["agents"])

def _check_ai():
    if not settings.openrouter_api_key:
        raise HTTPException(503, "AI not configured — set OPENROUTER_API_KEY in .env")


# ── Agent status ────────────────────────────────────────────
@router.get("/status")
async def agent_status(workspace_id: str, current_user: User = Depends(get_current_user)):
    agent_defs = [
        ("task", "auto", "Extracts tasks from messages"),
        ("project_manager", "on-demand", "Analyzes project health and blockers"),
        ("docs", "on-demand", "Drafts and improves documents"),
        ("knowledge", "on-demand", "Answers questions about your workspace"),
        ("digest", "scheduled", "Daily morning workspace summary"),
    ]
    return {
        "agents": [
            {
                "type": t,
                "model": models_for_profile(profile_for_agent_type(t))[0],
                "model_chain": models_for_profile(profile_for_agent_type(t)),
                "trigger": trigger,
                "description": desc,
            }
            for t, trigger, desc in agent_defs
        ],
        "fallback_model": settings.openrouter_fallback_model,
        "ai_enabled": bool(settings.openrouter_api_key),
    }


# ── Task Agent ───────────────────────────────────────────────
class TaskExtractRequest(BaseModel):
    message: str

@router.post("/task/run")
async def run_task_agent(
    workspace_id: str,
    body: TaskExtractRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ai()
    agent = TaskAgent()
    tasks = agent.extract(body.message)
    return {"agent": "task", "tasks": tasks, "count": len(tasks)}


# ── Project Manager Agent ────────────────────────────────────
class ProjectAnalysisRequest(BaseModel):
    project_id: str
    project_name: str

@router.post("/project_manager/run")
async def run_pm_agent(
    workspace_id: str,
    body: ProjectAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ai()
    result = await db.execute(
        select(Task).where(Task.project_id == uuid.UUID(body.project_id))
    )
    tasks = result.scalars().all()
    task_dicts = [
        {
            "title": t.title,
            "status": str(t.status.value if hasattr(t.status, 'value') else t.status),
            "priority": str(t.priority.value if hasattr(t.priority, 'value') else t.priority),
            "due_date": str(t.due_date) if t.due_date else None,
        }
        for t in tasks
    ]
    agent = ProjectManagerAgent()
    analysis = agent.analyze(body.project_name, task_dicts)
    return {"agent": "project_manager", **analysis}


# ── Docs Agent ───────────────────────────────────────────────
class DocsRequest(BaseModel):
    action: str  # "draft" | "summarize" | "improve"
    content: Optional[str] = None      # outline for draft, doc content for improve
    channel_id: Optional[str] = None   # for summarize

@router.post("/docs/run")
async def run_docs_agent(
    workspace_id: str,
    body: DocsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ai()
    agent = DocsAgent()

    if body.action == "draft":
        if not body.content:
            raise HTTPException(400, "content required for draft")
        result = agent.draft(body.content)
        return {"agent": "docs", "action": "draft", "content": result}

    elif body.action == "summarize":
        if not body.channel_id:
            raise HTTPException(400, "channel_id required for summarize")
        # Fetch channel name
        ch_result = await db.execute(select(Channel).where(Channel.id == uuid.UUID(body.channel_id)))
        channel = ch_result.scalar_one_or_none()
        ch_name = channel.name if channel else "unknown"
        # Fetch recent messages (last 50)
        msg_result = await db.execute(
            select(Message, User.name.label("author_name"))
            .join(User, User.id == Message.author_id)
            .where(and_(Message.channel_id == uuid.UUID(body.channel_id), Message.deleted_at.is_(None)))
            .order_by(Message.created_at.desc())
            .limit(50)
        )
        rows = msg_result.all()
        msgs = [{"content": r.Message.content, "author_name": r.author_name, "created_at": r.Message.created_at.isoformat()} for r in reversed(rows)]
        result = agent.summarize_channel(ch_name, msgs)
        return {"agent": "docs", "action": "summarize", "content": result, "channel_name": ch_name}

    elif body.action == "improve":
        if not body.content:
            raise HTTPException(400, "content required for improve")
        result = agent.improve(body.content)
        return {"agent": "docs", "action": "improve", "content": result}

    raise HTTPException(400, f"Unknown action: {body.action}")


# ── Knowledge Agent ──────────────────────────────────────────
class KnowledgeRequest(BaseModel):
    question: str
    channel_id: Optional[str] = None

@router.post("/knowledge/run")
async def run_knowledge_agent(
    workspace_id: str,
    body: KnowledgeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_ai()
    ws_id = uuid.UUID(workspace_id)
    term = f"%{body.question[:100]}%"

    # Fetch memories for context injection
    memories = await get_memories(db, workspace_id, limit=20)
    existing_keys = [m["key"] for m in memories]

    # Search messages
    msg_q = (
        select(Message, User.name.label("author_name"))
        .join(User, User.id == Message.author_id)
        .where(and_(
            Message.deleted_at.is_(None),
            Message.content.ilike(term),
        ))
        .order_by(Message.created_at.desc())
        .limit(15)
    )
    if body.channel_id:
        msg_q = msg_q.where(Message.channel_id == uuid.UUID(body.channel_id))
    msg_result = await db.execute(msg_q)
    msgs = [
        {"content": r.Message.content, "author_name": r.author_name, "created_at": r.Message.created_at.isoformat()}
        for r in msg_result.all()
    ]

    # Search docs
    doc_result = await db.execute(
        select(Document).where(
            and_(Document.workspace_id == ws_id, Document.title.ilike(term))
        ).limit(5)
    )
    docs = [{"title": d.title, "content": d.content} for d in doc_result.scalars().all()]

    agent = KnowledgeAgent()
    # Inject memories into knowledge agent context
    if memories:
        memory_agent = MemoryAgent()
        memory_section = memory_agent.format_for_context(memories)
        agent.system_prompt = agent.system_prompt + f"\n\n{memory_section}"

    result = agent.answer(body.question, msgs, docs)

    # Background: extract new facts from this Q&A
    async def _extract(q: str, a: str, keys: list[str]):
        try:
            from db.session import AsyncSessionLocal
            mem_agent = MemoryAgent()
            new_mems = mem_agent.extract(f"User asked: {q}\nAnswer: {a}", keys)
            if new_mems:
                async with AsyncSessionLocal() as session:
                    await upsert_memories(session, workspace_id, new_mems, source="ai")
        except Exception as e:
            logger.warning(f"[memory] knowledge extract failed: {e}")

    background_tasks.add_task(_extract, body.question, result.get("answer", ""), existing_keys)

    return {"agent": "knowledge", **result}


# ── Digest Agent (manual trigger for testing) ────────────────
@router.post("/digest/run")
async def run_digest_agent(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger the digest agent (normally runs on schedule)."""
    _check_ai()
    from agents.digest_agent import DigestAgent
    from models.other import Notification

    ws_result = await db.execute(select(Workspace).where(Workspace.id == uuid.UUID(workspace_id)))
    workspace = ws_result.scalar_one_or_none()
    ws_name = workspace.name if workspace else "Your Workspace"

    # Overdue tasks
    overdue_result = await db.execute(
        select(Task, User.name.label("assignee_name"))
        .outerjoin(User, User.id == Task.assignee_id)
        .where(and_(
            Task.workspace_id == uuid.UUID(workspace_id),
            Task.status.notin_([TaskStatus.done, TaskStatus.cancelled]),
            Task.due_date < date.today(),
        ))
        .limit(5)
    )
    overdue = [{"title": r.Task.title, "assignee_name": r.assignee_name} for r in overdue_result.all()]

    # Due today
    due_today_result = await db.execute(
        select(Task, User.name.label("assignee_name"))
        .outerjoin(User, User.id == Task.assignee_id)
        .where(and_(
            Task.workspace_id == uuid.UUID(workspace_id),
            Task.status.notin_([TaskStatus.done, TaskStatus.cancelled]),
            Task.due_date == date.today(),
        ))
        .limit(5)
    )
    due_today = [{"title": r.Task.title, "assignee_name": r.assignee_name} for r in due_today_result.all()]

    # Completed yesterday
    done_yesterday_result = await db.execute(
        select(Task)
        .where(and_(
            Task.workspace_id == uuid.UUID(workspace_id),
            Task.status == TaskStatus.done,
            Task.due_date == date.today() - timedelta(days=1),
        ))
        .limit(5)
    )
    done_yesterday = [{"title": t.title} for t in done_yesterday_result.scalars().all()]

    # Message count — use 0 to avoid complex interval casting
    msg_count = 0

    agent = DigestAgent()
    digest_text = agent.generate(ws_name, overdue, due_today, msg_count, done_yesterday)

    # Find or create #digest channel
    digest_ch = await db.execute(
        select(Channel).where(and_(
            Channel.workspace_id == uuid.UUID(workspace_id),
            Channel.name == "digest",
        ))
    )
    digest_channel = digest_ch.scalar_one_or_none()

    # Get workspace members for notifications
    members_result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == uuid.UUID(workspace_id))
    )
    member_ids = [m.user_id for m in members_result.scalars().all()]

    if not digest_channel:
        digest_channel = Channel(
            workspace_id=uuid.UUID(workspace_id),
            name="digest",
            type=ChannelType.public,
            created_by=member_ids[0] if member_ids else uuid.uuid4(),
        )
        db.add(digest_channel)
        await db.flush()

    # Post digest as a message from the first member (system message)
    if member_ids:
        msg = Message(
            channel_id=digest_channel.id,
            author_id=member_ids[0],
            content=digest_text,
        )
        db.add(msg)

    # Create notification for all members
    for uid in member_ids[:10]:
        notif = Notification(
            user_id=uid,
            type="digest",
            entity_type="channel",
            entity_id=digest_channel.id,
            message="Your daily digest is ready in #digest",
        )
        db.add(notif)

    await db.commit()
    return {"agent": "digest", "content": digest_text, "channel": "digest"}


# ── Memory CRUD ─────────────────────────────────────────────

class MemoryCreateRequest(BaseModel):
    key: str
    content: str
    importance: int = 3   # 1-5


@router.get("/memory")
async def list_memories(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all workspace memories ordered by importance."""
    memories = await get_memories(db, workspace_id, limit=100)
    return {"memories": memories, "count": len(memories)}


@router.post("/memory")
async def add_memory(
    workspace_id: str,
    body: MemoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually add or update a workspace memory."""
    count = await upsert_memories(
        db, workspace_id,
        [{"key": body.key, "content": body.content, "importance": body.importance}],
        source="manual",
    )
    if count == 0:
        raise HTTPException(400, "Failed to save memory")
    return {"ok": True}


@router.delete("/memory/{memory_id}")
async def remove_memory(
    workspace_id: str,
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a workspace memory by id."""
    ok = await delete_memory(db, workspace_id, memory_id)
    if not ok:
        raise HTTPException(404, "Memory not found")
    return {"ok": True}


async def _run_all_workspace_digests():
    """Called by scheduler — runs digest only for DIGEST_WORKSPACE_IDS (allowlist)."""
    from db.session import AsyncSessionLocal
    import logging
    logger = logging.getLogger(__name__)
    if not settings.openrouter_api_key:
        return
    allow = settings.digest_workspace_uuid_list()
    if not allow:
        logger.info("[digest] skipped: DIGEST_WORKSPACE_IDS is empty")
        return
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Workspace).where(Workspace.id.in_(allow)))
            workspaces = result.scalars().all()
            found_ids = {ws.id for ws in workspaces}
            for missing in allow:
                if missing not in found_ids:
                    logger.warning(f"[digest] workspace id not in DB: {missing}")
            for ws in workspaces:
                try:
                    # Create a fake current_user from first member
                    m_result = await db.execute(
                        select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id).limit(1)
                    )
                    member = m_result.scalar_one_or_none()
                    if member:
                        u_result = await db.execute(select(User).where(User.id == member.user_id))
                        user = u_result.scalar_one_or_none()
                        if user:
                            await run_digest_agent(str(ws.id), db, user)
                            logger.info(f"Digest sent for workspace {ws.name}")
                except Exception as e:
                    logger.warning(f"Digest failed for workspace {ws.id}: {e}")
    except Exception as e:
        logger.error(f"Scheduler digest error: {e}")
