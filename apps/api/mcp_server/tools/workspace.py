"""
MCP tools for workspace-level operations.

lno_list_workspaces          — discovery tool, MUST be first call each session
lno_get_workspace_snapshot   — read, executes immediately
lno_get_workspace_memory     — read, executes immediately
lno_upsert_workspace_memory  — low-risk write, executes immediately (agent memory)
"""
import re
import uuid
from sqlalchemy import select, or_
from db.session import AsyncSessionLocal
from models import Workspace, WorkspaceMember, User, Task, Project
from models.other import WorkspaceMemory
from mcp_server.server import mcp, agent_broadcast


@mcp.tool()
async def lno_list_workspaces() -> list[dict]:
    """
    Return all workspaces in LNO OS.
    ALWAYS call this first to get workspace IDs before any other tool.
    Never hardcode or guess workspace IDs — they change per deployment.
    Returns: [{"workspace_id": "<uuid>", "name": "...", "slug": "..."}]
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Workspace).order_by(Workspace.created_at.asc())
        )
        workspaces = [
            {
                "workspace_id": str(ws.id),
                "name": ws.name,
                "slug": ws.slug,
            }
            for ws in result.scalars().all()
        ]

    # Broadcast discovery event to all workspaces
    for ws in workspaces:
        await agent_broadcast(
            ws["workspace_id"],
            "lno_list_workspaces",
            "done",
            f"Discovered {len(workspaces)} workspace(s)",
        )
    return workspaces


@mcp.tool()
async def lno_get_workspace_snapshot(workspace_id: str) -> dict:
    """
    Return a high-level snapshot: member list, project summary, task counts by status.
    Call this at the start of any analysis run to understand the workspace state.
    """
    await agent_broadcast(workspace_id, "lno_get_workspace_snapshot", "running",
                          "Fetching workspace snapshot")

    ws_uuid = uuid.UUID(workspace_id)
    async with AsyncSessionLocal() as db:
        ws_result = await db.execute(select(Workspace).where(Workspace.id == ws_uuid))
        workspace = ws_result.scalar_one_or_none()
        ws_name = workspace.name if workspace else "Unknown"

        member_result = await db.execute(
            select(WorkspaceMember, User.name.label("name"), User.email.label("email"))
            .join(User, User.id == WorkspaceMember.user_id)
            .where(WorkspaceMember.workspace_id == ws_uuid)
        )
        members = [
            {
                "id": str(r.WorkspaceMember.user_id),
                "name": r.name,
                "email": r.email,
                "role": str(r.WorkspaceMember.role.value if hasattr(r.WorkspaceMember.role, "value") else r.WorkspaceMember.role),
            }
            for r in member_result.all()
        ]

        task_result = await db.execute(select(Task).where(Task.workspace_id == ws_uuid))
        tasks = task_result.scalars().all()
        task_counts: dict = {}
        for t in tasks:
            s = str(t.status.value if hasattr(t.status, "value") else t.status)
            task_counts[s] = task_counts.get(s, 0) + 1

        project_result = await db.execute(select(Project).where(Project.workspace_id == ws_uuid))
        all_projects = project_result.scalars().all()
        projects = [
            {"id": str(p.id), "name": p.name, "status": p.status}
            for p in all_projects[:10]
        ]

    result_dict = {
        "workspace_id": workspace_id,
        "workspace_name": ws_name,
        "member_count": len(members),
        "members": members,
        "task_counts": task_counts,
        "total_tasks": len(tasks),
        "projects": projects,
        "total_projects": len(all_projects),
    }
    await agent_broadcast(workspace_id, "lno_get_workspace_snapshot", "done",
                          f"{ws_name}: {len(members)} members, {len(all_projects)} projects")
    return result_dict


@mcp.tool()
async def lno_get_workspace_memory(workspace_id: str, limit: int = 30) -> list[dict]:
    """
    Retrieve workspace memories — facts previously stored about this workspace.
    Sorted by importance (5=highest). Use to check past findings before taking action.
    """
    await agent_broadcast(workspace_id, "lno_get_workspace_memory", "running",
                          "Reading workspace memory")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkspaceMemory)
            .where(WorkspaceMemory.workspace_id == uuid.UUID(workspace_id))
            .order_by(WorkspaceMemory.importance.desc(), WorkspaceMemory.updated_at.desc())
            .limit(limit)
        )
        memories = [
            {
                "key": m.key,
                "content": m.content,
                "importance": m.importance,
                "source": m.source,
            }
            for m in result.scalars().all()
        ]

    await agent_broadcast(workspace_id, "lno_get_workspace_memory", "done",
                          f"Read {len(memories)} memories")
    return memories


@mcp.tool()
async def lno_search_workspace_memory(
    workspace_id: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """
    Search workspace memory by keyword/topic. Matches the query terms against
    memory keys and content (case-insensitive), ranked by relevance + importance.
    Use this instead of lno_get_workspace_memory when you want a specific topic
    (e.g. "razorpay settlements", "ashik timezone") rather than the whole list.
    Returns up to `limit` matches: [{key, content, importance, source, score}].
    """
    terms = [t for t in re.split(r"\s+", (query or "").strip().lower()) if t]
    if not terms:
        return []

    await agent_broadcast(workspace_id, "lno_search_workspace_memory", "running",
                          f"Searching memory for '{query[:40]}'")

    async with AsyncSessionLocal() as db:
        conditions = []
        for t in terms:
            like = f"%{t}%"
            conditions.append(WorkspaceMemory.key.ilike(like))
            conditions.append(WorkspaceMemory.content.ilike(like))
        result = await db.execute(
            select(WorkspaceMemory)
            .where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                or_(*conditions),
            )
            .order_by(WorkspaceMemory.importance.desc())
            .limit(200)  # candidate cap; precise ranking happens below
        )
        rows = result.scalars().all()

    # Rank in Python: key matches weigh more than content matches, then importance.
    scored: list[tuple[float, WorkspaceMemory]] = []
    for m in rows:
        key_l = m.key.lower()
        content_l = (m.content or "").lower()
        hits = 0.0
        for t in terms:
            if t in key_l:
                hits += 2.0          # a hit in the key is a strong topic signal
            elif t in content_l:
                hits += 1.0
        if hits == 0:
            continue
        # Bonus for covering all query terms; importance breaks ties.
        coverage = sum(1 for t in terms if t in key_l or t in content_l) / len(terms)
        score = hits + coverage + (m.importance or 0) * 0.5
        scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = [
        {
            "key": m.key,
            "content": m.content,
            "importance": m.importance,
            "source": m.source,
            "score": round(score, 2),
        }
        for score, m in scored[: max(1, limit)]
    ]

    await agent_broadcast(workspace_id, "lno_search_workspace_memory", "done",
                          f"Found {len(out)} matches for '{query[:40]}'")
    return out


@mcp.tool()
async def lno_semantic_search_workspace_memory(
    workspace_id: str,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """
    Hybrid semantic + keyword search over workspace memory. Finds relevant facts
    even when the wording differs from how they were stored (e.g. "who runs
    finance" matches "Shaan owns the ledger"). Combines vector similarity with
    keyword matching, merged by reciprocal rank fusion. Falls back to keyword-only
    if embeddings are unavailable. Prefer this over lno_search_workspace_memory for
    conceptual/topic questions. Returns up to `limit` matches.
    """
    from core.memory_search import hybrid_search

    if not (query or "").strip():
        return []

    await agent_broadcast(workspace_id, "lno_semantic_search_workspace_memory", "running",
                          f"Semantic search: '{query[:40]}'")

    async with AsyncSessionLocal() as db:
        results = await hybrid_search(db, workspace_id, query, limit=limit)

    await agent_broadcast(workspace_id, "lno_semantic_search_workspace_memory", "done",
                          f"Found {len(results)} matches for '{query[:40]}'")
    return results


@mcp.tool()
async def lno_upsert_workspace_memory(
    workspace_id: str,
    key: str,
    content: str,
    importance: int = 3,
) -> dict:
    """
    Store or update a workspace memory. Executes immediately (agent's own memory).
    key: dot-namespaced e.g. "ops.last_scan.timestamp", "team.ashik.timezone"
    importance: 1-5 (5=critical business fact, 1=minor observation)
    Returns: {"ok": true, "key": key}
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import func
    from core.embeddings import aembed_text, memory_embedding_input
    from core.memory_search import find_near_duplicates

    # Best-effort embedding for semantic search (None if embeddings unavailable).
    embedding = await aembed_text(memory_embedding_input(key, content))

    async with AsyncSessionLocal() as db:
        # Phase 2: surface likely duplicates (other keys with near-identical meaning)
        # so the agent/gardener can consolidate. We never auto-merge here.
        near_duplicates = await find_near_duplicates(
            db, workspace_id, embedding, exclude_key=key
        )

        stmt = pg_insert(WorkspaceMemory).values(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(workspace_id),
            key=key,
            content=content,
            importance=max(1, min(5, importance)),
            source="hermes",
            embedding=embedding,
        ).on_conflict_do_update(
            constraint="uq_workspace_memory_key",
            set_={
                "content": content,
                "importance": max(1, min(5, importance)),
                "source": "hermes",
                "embedding": embedding,
                "updated_at": func.now(),
            },
        )
        await db.execute(stmt)
        await db.commit()

    await agent_broadcast(workspace_id, "lno_upsert_workspace_memory", "done",
                          f"Stored memory: {key}")
    result = {"ok": True, "key": key}
    if near_duplicates:
        result["near_duplicates"] = near_duplicates
    return result


@mcp.tool()
async def lno_delete_workspace_memory(workspace_id: str, key: str) -> dict:
    """
    Delete a workspace memory by key. Executes immediately (agent's own memory).
    Use during memory maintenance to prune duplicates, merged-away pages, or stale
    facts. Prefer merging content into a canonical key first, then deleting the
    redundant keys. Returns: {"ok": true, "key": key, "deleted": <count>}.
    """
    from sqlalchemy import delete as sa_delete

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            sa_delete(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMemory.key == key,
            )
        )
        await db.commit()
        deleted = result.rowcount or 0

    await agent_broadcast(workspace_id, "lno_delete_workspace_memory", "done",
                          f"Deleted memory: {key}" if deleted else f"No memory found: {key}")
    return {"ok": True, "key": key, "deleted": deleted}
