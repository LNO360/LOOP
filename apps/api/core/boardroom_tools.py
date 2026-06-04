"""
Boardroom tool layer.

A curated, extensible catalog of tools that boardroom agents can call during a
debate. Unlike the MCP tools (which run over the MCP transport via a Hermes
session), these are plain async handlers invoked directly inside the orchestrator's
tool-loop — fast and cheap enough to run for N agents × R rounds.

Each tool declares:
  - name        : function name exposed to the model
  - category    : research | workspace_read | workspace_write | calc
  - label       : human label for the UI picker
  - description : human description for the UI picker
  - schema      : OpenAI-style function schema (passed to chat_with_fallback)
  - handler     : async (workspace_id, **args) -> dict | list
  - risk        : low | medium  (write tools are medium)

Public API:
  - CATALOG          : list[dict] serializable subset for the UI
  - tool_names()     : set[str] of valid names
  - tool_schemas(names) -> list[dict]
  - execute_tool(name, workspace_id, args) -> dict
"""
from __future__ import annotations

import ast
import operator
import uuid
from typing import Any, Awaitable, Callable

from sqlalchemy import select

from db.session import AsyncSessionLocal
from core.web_research import brave_search, fetch_page


# ── Handlers ────────────────────────────────────────────────────────────────


async def _h_web_search(workspace_id: str, query: str, max_results: int = 5) -> dict:
    results = await brave_search(workspace_id, query, max_results)
    return {"results": results}


async def _h_web_fetch_page(workspace_id: str, url: str, max_chars: int = 4000) -> dict:
    return await fetch_page(url, max_chars)


async def _h_list_tasks(workspace_id: str, status: str | None = None, limit: int = 30) -> dict:
    from models import Task, TaskStatus, Project, User

    async with AsyncSessionLocal() as db:
        q = (
            select(Task, User.name.label("assignee_name"), Project.name.label("project_name"))
            .outerjoin(User, User.id == Task.assignee_id)
            .outerjoin(Project, Project.id == Task.project_id)
            .where(Task.workspace_id == uuid.UUID(workspace_id))
        )
        if status:
            try:
                q = q.where(Task.status == TaskStatus(status))
            except ValueError:
                return {"error": f"invalid status '{status}'; use todo|in_progress|done|cancelled"}
        q = q.order_by(Task.created_at.desc()).limit(min(limit, 100))
        rows = (await db.execute(q)).all()

    def _val(x):
        return x.value if hasattr(x, "value") else x

    return {
        "tasks": [
            {
                "title": r.Task.title,
                "status": _val(r.Task.status),
                "priority": _val(r.Task.priority),
                "assignee": r.assignee_name,
                "project": r.project_name,
                "due_date": r.Task.due_date.isoformat() if r.Task.due_date else None,
            }
            for r in rows
        ]
    }


async def _h_list_projects(workspace_id: str, limit: int = 20) -> dict:
    from models import Project

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(Project)
                .where(Project.workspace_id == uuid.UUID(workspace_id))
                .order_by(Project.created_at.desc())
                .limit(min(limit, 50))
            )
        ).scalars().all()

    def _val(x):
        return x.value if hasattr(x, "value") else x

    return {
        "projects": [
            {
                "name": p.name,
                "description": getattr(p, "description", None),
                "status": _val(getattr(p, "status", None)),
            }
            for p in rows
        ]
    }


async def _h_finance_summary(workspace_id: str) -> dict:
    from services import finance_service

    async with AsyncSessionLocal() as db:
        overview = await finance_service.get_overview(db, uuid.UUID(workspace_id))

    # Return dollars for readability by the model.
    def _d(cents: int) -> float:
        return round((cents or 0) / 100, 2)

    return {
        "cash_position": _d(overview["cash_position_cents"]),
        "mtd_revenue": _d(overview["mtd_revenue_cents"]),
        "mtd_expense": _d(overview["mtd_expense_cents"]),
        "mtd_net": _d(overview["mtd_net_cents"]),
        "unpaid_invoices_count": overview["unpaid_invoices_count"],
        "unpaid_invoices_total": _d(overview["unpaid_invoices_total_cents"]),
        "currency": "USD",
    }


async def _h_propose_task(
    workspace_id: str,
    title: str,
    description: str | None = None,
    priority: str = "medium",
) -> dict:
    """Create a pending ProposedAction (gated on human approval) — does NOT mutate."""
    from models.agent import ProposedAction

    if priority not in ("low", "medium", "high", "urgent"):
        priority = "medium"

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="create_task",
            payload={
                "title": title[:200],
                "description": description,
                "priority": priority,
                "source": "boardroom",
            },
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        await db.refresh(action)

    return {
        "proposed": True,
        "proposed_action_id": str(action.id),
        "note": "Task proposed for human approval — not yet created.",
    }


# ── Safe calculator ─────────────────────────────────────────────────────────

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numeric constants allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


async def _h_calculate(workspace_id: str, expression: str) -> dict:
    """Evaluate a pure arithmetic expression (no names, calls, or attributes)."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree.body)
    except ZeroDivisionError:
        return {"error": "division by zero"}
    except Exception:
        return {"error": "invalid arithmetic expression (numbers and + - * / // % ** only)"}
    return {"expression": expression, "result": result}


# ── Catalog ──────────────────────────────────────────────────────────────────

_TOOLS: dict[str, dict[str, Any]] = {
    "web_search": {
        "category": "research",
        "label": "Web search",
        "description": "Search the web (Brave) for outside evidence.",
        "risk": "low",
        "handler": _h_web_search,
        "schema": {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for evidence to support or challenge an argument. Returns titles, urls, and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Max results (default 5)"},
                    },
                    "required": ["query"],
                },
            },
        },
    },
    "web_fetch_page": {
        "category": "research",
        "label": "Read web page",
        "description": "Fetch and read the full text of a URL found via search.",
        "risk": "low",
        "handler": _h_web_fetch_page,
        "schema": {
            "type": "function",
            "function": {
                "name": "web_fetch_page",
                "description": "Fetch the clean text of a web page (use after web_search to read a result in full).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                        "max_chars": {"type": "integer", "description": "Truncate to N chars (default 4000)"},
                    },
                    "required": ["url"],
                },
            },
        },
    },
    "list_tasks": {
        "category": "workspace_read",
        "label": "List tasks",
        "description": "Read the workspace's tasks to ground the debate in real work.",
        "risk": "low",
        "handler": _h_list_tasks,
        "schema": {
            "type": "function",
            "function": {
                "name": "list_tasks",
                "description": "List tasks in this workspace. Optionally filter by status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "description": "todo|in_progress|done|cancelled"},
                        "limit": {"type": "integer", "description": "Max tasks (default 30)"},
                    },
                },
            },
        },
    },
    "list_projects": {
        "category": "workspace_read",
        "label": "List projects",
        "description": "Read the workspace's projects.",
        "risk": "low",
        "handler": _h_list_projects,
        "schema": {
            "type": "function",
            "function": {
                "name": "list_projects",
                "description": "List projects in this workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Max projects (default 20)"},
                    },
                },
            },
        },
    },
    "finance_summary": {
        "category": "workspace_read",
        "label": "Finance summary",
        "description": "Read cash position, month-to-date revenue/expense, and unpaid invoices.",
        "risk": "low",
        "handler": _h_finance_summary,
        "schema": {
            "type": "function",
            "function": {
                "name": "finance_summary",
                "description": "Get the workspace finance summary: cash position, MTD revenue/expense/net, unpaid invoices (USD).",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    },
    "propose_task": {
        "category": "workspace_write",
        "label": "Propose task",
        "description": "Propose a task for human approval (does not create it directly).",
        "risk": "medium",
        "handler": _h_propose_task,
        "schema": {
            "type": "function",
            "function": {
                "name": "propose_task",
                "description": "Propose a follow-up task. Creates a pending proposal for human approval — it is NOT created until a human approves.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {"type": "string", "description": "low|medium|high|urgent"},
                    },
                    "required": ["title"],
                },
            },
        },
    },
    "calculate": {
        "category": "calc",
        "label": "Calculator",
        "description": "Evaluate arithmetic for quantitative arguments.",
        "risk": "low",
        "handler": _h_calculate,
        "schema": {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Evaluate a pure arithmetic expression (numbers and + - * / // % ** only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "e.g. (1200 * 12) / 0.85"},
                    },
                    "required": ["expression"],
                },
            },
        },
    },
}


# Serializable subset for the UI picker.
CATALOG: list[dict] = [
    {
        "name": name,
        "category": spec["category"],
        "label": spec["label"],
        "description": spec["description"],
        "risk": spec["risk"],
    }
    for name, spec in _TOOLS.items()
]


def tool_names() -> set[str]:
    return set(_TOOLS.keys())


def tool_schemas(names: list[str]) -> list[dict]:
    """Return OpenAI function schemas for the named tools (unknown names skipped)."""
    return [_TOOLS[n]["schema"] for n in names if n in _TOOLS]


async def execute_tool(name: str, workspace_id: str, args: dict | None) -> dict:
    """Dispatch a tool call. Never raises — returns {"error": ...} on failure."""
    spec = _TOOLS.get(name)
    if not spec:
        return {"error": f"unknown tool '{name}'"}
    handler: Callable[..., Awaitable[Any]] = spec["handler"]
    try:
        result = await handler(workspace_id, **(args or {}))
        return result if isinstance(result, dict) else {"result": result}
    except TypeError as e:
        return {"error": f"bad arguments for '{name}': {e}"}
    except Exception as e:  # pragma: no cover - defensive
        return {"error": f"tool '{name}' failed: {str(e)[:200]}"}
