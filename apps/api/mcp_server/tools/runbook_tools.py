"""
MCP tools for saved, replayable runbooks.

A runbook is a named JSON recipe of ordered steps. Execution RETURNS the resolved
plan — it does not dispatch tools server-side — so the agent runs each step with
its normal tool calls and destructive steps still flow through human approval.

lno_create_runbook  — save a runbook (name + steps).
lno_list_runbooks   — list saved runbooks.
lno_execute_runbook — fetch a runbook and return its ordered steps to run.

Runbooks ride on WorkspaceMemory: key "hermes.runbook.<slug>", content = JSON of
{"name", "description", "steps": [{"tool", "params", "note"}]}, source "runbook".
"""
import json
import re
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

from db.session import AsyncSessionLocal
from models.other import WorkspaceMemory
from mcp_server.server import mcp, agent_broadcast

RUNBOOK_KEY_PREFIX = "hermes.runbook."


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-")[:60]


def _validate_steps(steps) -> tuple[bool, str]:
    """Each step must be a dict with a non-empty string 'tool'. params/note optional."""
    if not isinstance(steps, list) or not steps:
        return False, "steps must be a non-empty list of {tool, params, note} dicts"
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step {i} is not an object"
        tool = step.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            return False, f"step {i} is missing a non-empty 'tool' name"
    return True, ""


def _normalize_steps(steps: list) -> list[dict]:
    return [
        {
            "tool": s["tool"],
            "params": s.get("params", {}),
            "note": s.get("note", ""),
        }
        for s in steps
    ]


@mcp.tool()
async def lno_create_runbook(
    workspace_id: str,
    name: str,
    steps: list,
    description: str = "",
) -> dict:
    """
    Save a reusable runbook.

    name: human name (e.g. "Weekly Digest"); slug is derived from it.
    steps: ordered list of {tool, params, note} — tool is the MCP tool name,
           params its arguments, note an optional human description.
    description: optional one-line summary.

    Returns: {"ok": true, "slug": "..."} or {"ok": false, "error": "..."}.
    """
    ok, err = _validate_steps(steps)
    if not ok:
        return {"ok": False, "error": err}

    slug = _slugify(name)
    if not slug:
        return {"ok": False, "error": "name must contain at least one alphanumeric character"}

    payload = json.dumps({
        "name": name,
        "description": description,
        "steps": _normalize_steps(steps),
    })

    async with AsyncSessionLocal() as db:
        await db.execute(pg_insert(WorkspaceMemory).values(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(workspace_id),
            key=RUNBOOK_KEY_PREFIX + slug,
            content=payload,
            importance=3,
            source="runbook",
        ).on_conflict_do_update(
            constraint="uq_workspace_memory_key",
            set_={"content": payload, "source": "runbook", "updated_at": func.now()},
        ))
        await db.commit()

    await agent_broadcast(workspace_id, "lno_create_runbook", "done",
                          f"Runbook '{name}' saved ({len(steps)} steps)")
    return {"ok": True, "slug": slug}


@mcp.tool()
async def lno_list_runbooks(workspace_id: str) -> dict:
    """
    List saved runbooks.
    Returns: {"ok": true, "runbooks": [{"name", "slug", "description", "step_count"}]}
    """
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMemory.key.like(RUNBOOK_KEY_PREFIX + "%"),
            ).order_by(WorkspaceMemory.updated_at.desc())
        )).scalars().all()

    runbooks = []
    for r in rows:
        try:
            data = json.loads(r.content)
        except (ValueError, TypeError):
            continue
        runbooks.append({
            "name": data.get("name", ""),
            "slug": r.key.removeprefix(RUNBOOK_KEY_PREFIX),
            "description": data.get("description", ""),
            "step_count": len(data.get("steps", [])),
        })
    return {"ok": True, "runbooks": runbooks, "total": len(runbooks)}


@mcp.tool()
async def lno_execute_runbook(workspace_id: str, name_or_slug: str) -> dict:
    """
    Resolve a runbook and return its ordered steps for you to execute.

    The steps are NOT run server-side — run each tool(params) yourself, so any
    destructive step still goes through the proposed-action approval flow.

    name_or_slug: the runbook slug, or its display name.
    Returns: {"ok": true, "name", "slug", "steps": [{tool, params, note}]}
             or {"ok": false, "error": "..."}.
    """
    slug = _slugify(name_or_slug)
    async with AsyncSessionLocal() as db:
        # Try exact slug first.
        row = (await db.execute(
            select(WorkspaceMemory).where(
                WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                WorkspaceMemory.key == RUNBOOK_KEY_PREFIX + slug,
            )
        )).scalar_one_or_none()

        # Fall back to matching the stored display name.
        if row is None:
            candidates = (await db.execute(
                select(WorkspaceMemory).where(
                    WorkspaceMemory.workspace_id == uuid.UUID(workspace_id),
                    WorkspaceMemory.key.like(RUNBOOK_KEY_PREFIX + "%"),
                )
            )).scalars().all()
            for c in candidates:
                try:
                    if json.loads(c.content).get("name", "").strip().lower() == name_or_slug.strip().lower():
                        row = c
                        break
                except (ValueError, TypeError):
                    continue

    if row is None:
        return {"ok": False, "error": f"runbook '{name_or_slug}' not found"}

    data = json.loads(row.content)
    resolved_slug = row.key.removeprefix(RUNBOOK_KEY_PREFIX)
    await agent_broadcast(workspace_id, "lno_execute_runbook", "running",
                          f"Runbook '{data.get('name', resolved_slug)}' started")
    return {
        "ok": True,
        "name": data.get("name", resolved_slug),
        "slug": resolved_slug,
        "steps": data.get("steps", []),
    }
