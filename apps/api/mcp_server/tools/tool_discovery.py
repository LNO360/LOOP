"""
Dynamic toolset meta-tools for Hermes.

lno_find_tools — discover domain tools by intent (not pre-loaded every session)
lno_invoke     — execute any registered tool by name
"""
from __future__ import annotations

import inspect
import json
from typing import Any, Optional

from mcp_server.server import mcp

# Tools always loaded in every Hermes session (from hermes/config.yaml tools.include).
# Keep in sync with that list. lno_find_tools and lno_invoke are excluded from
# discovery results so the model doesn't recurse into them.
CORE_TOOLS: frozenset[str] = frozenset({
    "lno_get_workspace_snapshot",
    "lno_list_tasks",
    "lno_list_overdue_tasks",
    "lno_create_task",
    "lno_update_task",
    "lno_list_projects",
    "lno_get_workspace_memory",
    "lno_upsert_workspace_memory",
    "lno_search_workspace_memory",
    "lno_semantic_search_workspace_memory",
    "lno_delete_workspace_memory",
    "lno_send_channel_message",
    "lno_create_notification",
    "lno_list_proposed_actions",
    "lno_approve_proposed_action",
    "lno_reject_proposed_action",
    "lno_read_skill",
    "lno_list_skills",
    "lno_find_tools",
    "lno_invoke",
})

# Maps category label → tool name prefix for direct filtering.
CATEGORY_PREFIXES: dict[str, str] = {
    "gmail": "gmail_",
    "drive": "gdrive_",
    "calendar": "gcal_",
    "github": "github_",
    "finance": "finance_",
    "web": "web_",
    "gsc": "gsc_",
    "search_console": "gsc_",
}


async def _await_if_needed(value: Any) -> Any:
    """FastMCP 2.14+ exposes async get_tool / has_tool / get_tools."""
    if inspect.isawaitable(value):
        return await value
    return value


async def _all_registered_tools() -> dict:
    tools = await _await_if_needed(mcp._tool_manager.get_tools())
    return tools


def _compact_usage(name: str, parameters: dict) -> str:
    """Build a compact one-line signature from a JSON schema — e.g. tool(a:string, b:integer=10)."""
    props = parameters.get("properties", {})
    required = set(parameters.get("required", []))
    parts = []
    for param, schema in props.items():
        ptype = schema.get("type", "any")
        default = schema.get("default")
        if param in required:
            parts.append(f"{param}:{ptype}")
        else:
            suffix = f"={default}" if default is not None else "?"
            parts.append(f"{param}:{ptype}{suffix}")
    return f"{name}({', '.join(parts)})"


@mcp.tool()
async def lno_find_tools(intent: str, category: Optional[str] = None) -> list[dict]:
    """
    Discover domain tools (gmail, drive, calendar, github, finance, web)
    that are not pre-loaded in every Hermes session.
    Pass a plain-English description of what you want to do — returns up to 4
    matching tools as {name, description, usage} where usage shows the arg signature.
    Then call lno_invoke(tool_name, {args}) to execute the chosen tool.
    category (optional): gmail | drive | calendar | github | finance | web
    Skip lno_find_tools if you already know the tool name from a previous turn.
    """
    all_tools = await _all_registered_tools()
    pool: dict = {name: tool for name, tool in all_tools.items() if name not in CORE_TOOLS}

    if category:
        prefix = CATEGORY_PREFIXES.get(category, "")
        if prefix:
            filtered = {n: t for n, t in pool.items() if n.startswith(prefix)}
            candidates = filtered if filtered else pool
        else:
            candidates = pool
    else:
        candidates = pool

    intent_words = set(intent.lower().split())

    def score(name: str, tool: Any) -> int:
        text = (name + " " + tool.description).lower()
        return sum(1 for w in intent_words if w in text)

    ranked = sorted(candidates.items(), key=lambda kv: score(kv[0], kv[1]), reverse=True)

    top_score = score(ranked[0][0], ranked[0][1]) if ranked else 0
    if top_score > 0:
        top = ranked[:4]
    else:
        # No keyword match — return up to 12 tools alphabetically so the model
        # can browse without overwhelming the context window.
        top = sorted(candidates.items())[:12]

    return [
        {
            "name": name,
            "description": next(
                (line.strip() for line in tool.description.splitlines() if line.strip()), ""
            ),
            "usage": _compact_usage(name, tool.parameters),
        }
        for name, tool in top
    ]


@mcp.tool()
async def lno_invoke(tool_name: str, args: dict) -> Any:
    """
    Execute any registered MCP tool by name with the provided args dict.
    Use lno_find_tools first to discover available tool names and their parameter
    schemas, then call this to execute the chosen tool.
    args: a dict matching the tool's parameters schema exactly.
    """
    tool_manager = mcp._tool_manager

    if not await _await_if_needed(tool_manager.has_tool(tool_name)):
        return {
            "error": (
                f"Tool '{tool_name}' not found. "
                "Call lno_find_tools to discover available tools."
            )
        }

    tool = await _await_if_needed(tool_manager.get_tool(tool_name))
    try:
        # Prefer fastmcp's run() (validation + ToolResult); fall back to raw fn.
        if hasattr(tool, "run"):
            result = await tool.run(args)
            structured = getattr(result, "structured_content", None)
            if isinstance(structured, dict) and "result" in structured:
                return structured["result"]
            if structured is not None:
                return structured
            content = getattr(result, "content", None)
            if content:
                text = "".join(
                    block.text for block in content if getattr(block, "text", None)
                )
                if text:
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
            return result
        result = tool.fn(**args)
        if inspect.isawaitable(result):
            result = await result
        return result
    except TypeError as e:
        return {"error": f"Invalid args for '{tool_name}': {e}"}
    except Exception as e:
        return {"error": f"Tool '{tool_name}' failed: {str(e)}"}
