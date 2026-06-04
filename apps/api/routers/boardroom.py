"""
Boardroom of Agents router.

POST   /workspaces/{id}/boardroom/sessions                  — create session
GET    /workspaces/{id}/boardroom/sessions                  — list sessions
GET    /workspaces/{id}/boardroom/sessions/{sid}            — get session
POST   /workspaces/{id}/boardroom/sessions/{sid}/start      — SSE stream discussion
POST   /workspaces/{id}/boardroom/sessions/{sid}/interject  — inject moderator turn
POST   /workspaces/{id}/boardroom/sessions/{sid}/stop       — pause/stop
GET    /workspaces/{id}/boardroom/sessions/{sid}/output     — get output
POST   /workspaces/{id}/boardroom/sessions/{sid}/apply      — create tasks from output
"""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core import boardroom_tools
from db.session import get_db
from models import User, Task, TaskPriority
from models.boardroom import BoardroomSession, BoardroomAgent
from agents.boardroom_orchestrator import (
    BoardroomOrchestrator,
    VALID_MODES,
    phase_for_round,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/boardroom",
    tags=["boardroom"],
)

# In-memory interject queues per running session (V1: single-server only)
_interject_queues: dict[str, asyncio.Queue] = {}

# Sessions whose owner clicked "Stop & summarize": the running stream finishes
# the current speaker, then jumps straight to synthesis. (single-server only)
_finish_requests: set[str] = set()


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class AgentIn(BaseModel):
    name: str
    emoji: str = "🤖"
    persona_type: str  # builtin | custom | adhoc
    agent_ref: Optional[str] = None
    system_prompt: str
    turn_order: int = 0
    tools: Optional[list[str]] = None  # None = inherit session default_tools


class CreateSessionRequest(BaseModel):
    topic: str
    rounds_config: int = 2
    debate_mode: str = "round_robin"  # round_robin | structured | dynamic
    default_tools: list[str] = []
    agents: list[AgentIn]


class InterjectRequest(BaseModel):
    message: str


class ApplyRequest(BaseModel):
    task_ids: Optional[list[int]] = None  # indices into proposed_tasks; None = all


# ── Serialisers ───────────────────────────────────────────────────────────────


def _agent_out(a: BoardroomAgent) -> dict:
    return {
        "id": str(a.id),
        "session_id": str(a.session_id),
        "name": a.name,
        "emoji": a.emoji,
        "persona_type": a.persona_type,
        "agent_ref": str(a.agent_ref) if a.agent_ref else None,
        "system_prompt": a.system_prompt,
        "turn_order": a.turn_order,
        "tools": a.tools,
    }


def _session_out(s: BoardroomSession, agents: list[BoardroomAgent] | None = None) -> dict:
    return {
        "id": str(s.id),
        "workspace_id": str(s.workspace_id),
        "topic": s.topic,
        "status": s.status,
        "rounds_config": s.rounds_config,
        "debate_mode": s.debate_mode,
        "default_tools": s.default_tools or [],
        "transcript": s.transcript or [],
        "output": s.output,
        "created_by": str(s.created_by) if s.created_by else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "agents": [_agent_out(a) for a in agents] if agents is not None else [],
    }


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/sessions", status_code=201)
async def create_session(
    workspace_id: str,
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not body.agents:
        raise HTTPException(400, "At least one agent is required")
    if not (1 <= body.rounds_config <= 5):
        raise HTTPException(400, "rounds_config must be between 1 and 5")
    if body.debate_mode not in VALID_MODES:
        raise HTTPException(400, f"debate_mode must be one of {sorted(VALID_MODES)}")

    valid_tools = boardroom_tools.tool_names()

    def _clean_tools(names: list[str] | None) -> list[str] | None:
        if names is None:
            return None
        bad = [n for n in names if n not in valid_tools]
        if bad:
            raise HTTPException(400, f"unknown tools: {bad}")
        return names

    default_tools = _clean_tools(body.default_tools) or []

    session = BoardroomSession(
        workspace_id=uuid.UUID(workspace_id),
        topic=body.topic,
        status="setup",
        rounds_config=body.rounds_config,
        debate_mode=body.debate_mode,
        default_tools=default_tools,
        transcript=[],
        created_by=current_user.id,
    )
    db.add(session)
    await db.flush()

    agents = []
    for i, a in enumerate(body.agents):
        agent = BoardroomAgent(
            session_id=session.id,
            name=a.name,
            emoji=a.emoji,
            persona_type=a.persona_type,
            agent_ref=uuid.UUID(a.agent_ref) if a.agent_ref else None,
            system_prompt=a.system_prompt,
            turn_order=a.turn_order if a.turn_order is not None else i,
            tools=_clean_tools(a.tools),
        )
        db.add(agent)
        agents.append(agent)

    await db.commit()
    return _session_out(session, agents)


@router.get("/tools")
async def list_tools(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
):
    """Catalog of tools agents can be given in this workspace."""
    return {"tools": boardroom_tools.CATALOG}


@router.get("/sessions")
async def list_sessions(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BoardroomSession)
        .where(BoardroomSession.workspace_id == uuid.UUID(workspace_id))
        .order_by(BoardroomSession.created_at.desc())
        .limit(50)
    )
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        agents_result = await db.execute(
            select(BoardroomAgent)
            .where(BoardroomAgent.session_id == s.id)
            .order_by(BoardroomAgent.turn_order)
        )
        agents = agents_result.scalars().all()
        out.append(_session_out(s, agents))
    return {"sessions": out, "count": len(out)}


@router.get("/sessions/{session_id}")
async def get_session(
    workspace_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, agents = await _load_session(workspace_id, session_id, db)
    return _session_out(session, agents)


@router.post("/sessions/{session_id}/start")
async def start_session(
    workspace_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, agents = await _load_session(workspace_id, session_id, db)
    if session.status not in ("setup", "paused"):
        raise HTTPException(400, f"Session is {session.status}, cannot start")
    if not agents:
        raise HTTPException(400, "No agents in session")

    session.status = "running"
    await db.commit()

    transcript: list[dict] = list(session.transcript or [])
    sid = str(session.id)
    topic = session.topic
    rounds_config = session.rounds_config
    debate_mode = session.debate_mode or "round_robin"
    default_tools = session.default_tools or []

    orchestrator = BoardroomOrchestrator(agents)
    orchestrator.bind_workspace(workspace_id)

    def _effective_tools(agent: BoardroomAgent) -> list[str]:
        return agent.tools if agent.tools is not None else default_tools

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        _interject_queues[sid] = queue

        from db.session import AsyncSessionLocal

        try:
            stop_early = False
            for round_num in range(rounds_config):
                if stop_early:
                    break
                if debate_mode == "structured":
                    yield _sse({
                        "type": "phase_start",
                        "phase": phase_for_round(round_num, rounds_config),
                        "round": round_num + 1,
                        "total_rounds": rounds_config,
                    })

                for agent in orchestrator.agents:
                    # Drain all pending interjections before this turn
                    while True:
                        try:
                            msg = queue.get_nowait()
                            turn = {
                                "role": "moderator",
                                "name": "Moderator",
                                "content": msg,
                                "round": round_num + 1,
                            }
                            transcript.append(turn)
                            yield _sse({"type": "interject_ack", "content": msg})
                            async with AsyncSessionLocal() as inner_db:
                                await _persist_transcript(sid, transcript, inner_db)
                        except asyncio.QueueEmpty:
                            break

                    # "Stop & summarize" requested → finish now and synthesize.
                    if sid in _finish_requests:
                        stop_early = True
                        yield _sse({"type": "stopping"})
                        break

                    # Check if paused between turns
                    async with AsyncSessionLocal() as check_db:
                        current_status = await _get_status(sid, check_db)
                    if current_status == "paused":
                        return

                    yield _sse(
                        {
                            "type": "turn_start",
                            "agent": {
                                "id": str(agent.id),
                                "name": agent.name,
                                "emoji": agent.emoji,
                            },
                            "round": round_num + 1,
                            "total_rounds": rounds_config,
                        }
                    )

                    full_text = ""
                    tool_events: list[dict] = []
                    turn_stopped = False
                    async for ev in orchestrator.run_turn(
                        agent, topic, transcript,
                        tools=_effective_tools(agent),
                        mode=debate_mode,
                        round_num=round_num,
                        total_rounds=rounds_config,
                        should_stop=lambda: sid in _finish_requests,
                    ):
                        if ev["type"] == "turn_complete":
                            full_text = ev["content"]
                            tool_events = ev.get("tool_events", [])
                            turn_stopped = ev.get("stopped", False)
                        else:
                            # tool_call / tool_result — stream to the client
                            yield _sse({**ev, "agent_id": str(agent.id)})

                    # Only record a turn if the agent actually produced an argument.
                    # A mid-turn "Stop & summarize" may cut off before any prose.
                    if full_text.strip():
                        turn = {
                            "role": "agent",
                            "agent_id": str(agent.id),
                            "name": agent.name,
                            "emoji": agent.emoji,
                            "content": full_text,
                            "round": round_num + 1,
                        }
                        if tool_events:
                            turn["tool_events"] = tool_events
                        transcript.append(turn)

                        async with AsyncSessionLocal() as inner_db:
                            await _persist_transcript(sid, transcript, inner_db)

                        yield _sse(
                            {
                                "type": "turn_end",
                                "agent_id": str(agent.id),
                                "full_text": full_text,
                                "tool_events": tool_events,
                            }
                        )

                    # Stop requested mid-turn → wrap up now.
                    if turn_stopped:
                        stop_early = True
                        yield _sse({"type": "stopping"})
                        break

                # Dynamic mode: moderator sharpens the disagreement between rounds.
                if not stop_early and debate_mode == "dynamic" and round_num < rounds_config - 1:
                    challenge = await orchestrator.moderator_challenge(topic, transcript)
                    if challenge:
                        turn = {
                            "role": "moderator",
                            "name": "Moderator",
                            "content": challenge,
                            "round": round_num + 1,
                        }
                        transcript.append(turn)
                        yield _sse({"type": "moderator_challenge", "content": challenge})
                        async with AsyncSessionLocal() as inner_db:
                            await _persist_transcript(sid, transcript, inner_db)

            # Synthesis — stream the decision brief as it's written so the user
            # sees the report build instead of waiting on a blank spinner.
            yield _sse({"type": "synthesis_start"})
            async with AsyncSessionLocal() as inner_db:
                await _set_status(sid, "synthesizing", inner_db)

            synthesis_text = ""
            async for delta in orchestrator.synthesize_stream(topic, transcript):
                synthesis_text += delta
                yield _sse({"type": "synthesis_delta", "text": delta})

            if synthesis_text.strip():
                output = orchestrator._parse_synthesis(synthesis_text)
            else:
                # Stream produced nothing (e.g. provider hiccup) → blocking fallback.
                output = await orchestrator.synthesize(topic, transcript)

            async with AsyncSessionLocal() as inner_db:
                await _persist_output(sid, output, inner_db)

            yield _sse(
                {
                    "type": "plan_ready",
                    "plan": output["plan"],
                    "proposed_tasks": output["proposed_tasks"],
                }
            )
            yield _sse({"type": "session_done"})

        finally:
            _interject_queues.pop(sid, None)
            _finish_requests.discard(sid)
            # Reset status to "paused" if client disconnected mid-stream
            async with AsyncSessionLocal() as cleanup_db:
                current = await _get_status(sid, cleanup_db)
                if current == "running":
                    await _set_status(sid, "paused", cleanup_db)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/interject")
async def interject(
    workspace_id: str,
    session_id: str,
    body: InterjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, _ = await _load_session(workspace_id, session_id, db)
    sid = str(session.id)

    if sid in _interject_queues:
        await _interject_queues[sid].put(body.message)
    else:
        # Session not currently streaming; append directly to transcript
        transcript = list(session.transcript or [])
        transcript.append(
            {"role": "moderator", "name": "Moderator", "content": body.message}
        )
        session.transcript = transcript
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()

    return {"ok": True, "message": body.message}


@router.post("/sessions/{session_id}/stop")
async def stop_session(
    workspace_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, _ = await _load_session(workspace_id, session_id, db)
    sid = str(session.id)

    # If the session is actively streaming, ask it to finish the current speaker
    # and jump to synthesis (the client keeps listening for the final report).
    if sid in _interject_queues:
        _finish_requests.add(sid)
        return {"ok": True, "status": "finishing"}

    # Not streaming → just pause (legacy behavior).
    session.status = "paused"
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True, "status": "paused"}


@router.get("/sessions/{session_id}/output")
async def get_output(
    workspace_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, _ = await _load_session(workspace_id, session_id, db)
    if not session.output:
        raise HTTPException(404, "No output yet — session has not completed synthesis")
    return session.output


@router.post("/sessions/{session_id}/apply")
async def apply_tasks(
    workspace_id: str,
    session_id: str,
    body: ApplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session, _ = await _load_session(workspace_id, session_id, db)
    if not session.output:
        raise HTTPException(400, "Session has no output yet")

    proposed = session.output.get("proposed_tasks", [])
    if body.task_ids is not None:
        tasks_to_create = [proposed[i] for i in body.task_ids if 0 <= i < len(proposed)]
    else:
        tasks_to_create = proposed

    created = []
    for t in tasks_to_create:
        priority_val = t.get("priority", "medium")
        if priority_val not in ("low", "medium", "high", "urgent"):
            priority_val = "medium"
        task = Task(
            workspace_id=uuid.UUID(workspace_id),
            title=t["title"][:200],
            description=t.get("description"),
            priority=TaskPriority(priority_val),
            created_by=current_user.id,
        )
        db.add(task)
        await db.flush()
        created.append({"id": str(task.id), "title": task.title, "priority": priority_val})

    await db.commit()
    return {"created": created, "count": len(created)}


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _load_session(
    workspace_id: str, session_id: str, db: AsyncSession
) -> tuple[BoardroomSession, list[BoardroomAgent]]:
    result = await db.execute(
        select(BoardroomSession).where(
            BoardroomSession.id == uuid.UUID(session_id),
            BoardroomSession.workspace_id == uuid.UUID(workspace_id),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    agents_result = await db.execute(
        select(BoardroomAgent)
        .where(BoardroomAgent.session_id == session.id)
        .order_by(BoardroomAgent.turn_order)
    )
    agents = list(agents_result.scalars().all())
    return session, agents


async def _persist_transcript(
    session_id: str, transcript: list[dict], db: AsyncSession
) -> None:
    result = await db.execute(
        select(BoardroomSession).where(BoardroomSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()
    if session:
        session.transcript = transcript
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def _persist_output(
    session_id: str, output: dict, db: AsyncSession
) -> None:
    result = await db.execute(
        select(BoardroomSession).where(BoardroomSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()
    if session:
        session.output = output
        session.status = "done"
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def _set_status(session_id: str, status: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(BoardroomSession).where(BoardroomSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()
    if session:
        session.status = status
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def _get_status(session_id: str, db: AsyncSession) -> str:
    result = await db.execute(
        select(BoardroomSession).where(BoardroomSession.id == uuid.UUID(session_id))
    )
    session = result.scalar_one_or_none()
    return session.status if session else "unknown"
