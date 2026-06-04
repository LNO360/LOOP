"""
LNO OS MCP Server — exposes LNO data to Hermes via the Model Context Protocol.

Mounted at /mcp on the FastAPI app.
Hermes connects via HTTP: url: "http://api:8000/mcp"
Auth: Bearer token in Authorization header, validated by ServiceTokenMiddleware.
"""
from fastmcp import FastMCP
from core.config import settings


# ── Auth middleware ────────────────────────────────────────────────────────────

class ServiceTokenMiddleware:
    """Validates every request to /mcp has Authorization: Bearer <token>."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")
        expected = f"Bearer {settings.get_hermes_token()}"

        if auth_header != expected:
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [[b"content-type", b"application/json"]],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"detail":"Unauthorized \xe2\x80\x94 invalid service token"}',
            })
            return

        await self.app(scope, receive, send)


# ── FastMCP instance ───────────────────────────────────────────────────────────

mcp = FastMCP(
    "lno-os",
    instructions=(
        "You are connected to LNO OS, an AI-native company operating system. "
        "Use the lno_* tools to read and write workspace data. "
        "Most lno_* write tools execute immediately (tasks, projects, channel messages, "
        "notifications, memory, blog drafts). Destructive operations (delete_task, delete_project, "
        "delete_message, delete_skill, lno_blog_publish, lno_site_redeploy) queue proposed_action "
        "for human approval. lno_site_list_published_urls shows blog URLs; lno_site_redeploy "
        "rebuilds the marketing site after new posts (Vercel + optional GitHub slug sync). "
        "gsc_* tools are read-only — cannot submit sitemaps to Google via MCP."
    ),
)

def register_mcp_tools() -> None:
    """
    Import all MCP tool modules so @mcp.tool() decorators register on `mcp`.

    Must be called after `mcp` is created and from outside this module (e.g. main.py).
    Importing tool modules inside server.py at module load time fails silently due to
    circular imports (tools import `mcp` from here while server is still initializing).
    """
    from mcp_server.tools import (  # noqa: F401
        boardroom,
        feedback_tools,
        finance_tools,
        github_tools,
        lno_blog_tools,
        lno_site_tools,
        memory_sync,
        messages,
        projects,
        proposed_actions_tools,
        runbook_tools,
        self_modify,
        tasks,
        tool_discovery,
        workspace,
        web_search,
        google_gmail,
        google_drive,
        google_calendar,
        google_search_console,
    )


def get_raw_mcp_app():
    """Return the raw FastMCP ASGI app (StarletteWithLifespan).
    Use this to wire the lifespan into the parent FastAPI app.

    fastmcp >= 2.3 exposes streamable HTTP via http_app(); older releases
    (e.g. 2.1.2) only have sse_app(). Use whichever exists so the app boots
    regardless of the installed fastmcp version.

    stateless_http=True is REQUIRED because the api runs under multiple uvicorn
    workers (--workers 4). MCP streamable-HTTP sessions are held in a single
    worker's memory; without stateless mode, a follow-up request load-balanced to
    a different worker can't find the session -> "Session terminated"/404, dropped
    connections, and Hermes giving up. Stateless mode creates a fresh transport
    context per request, eliminating the need for worker session affinity.
    (fastmcp docs: Production Deployment > Horizontal Scaling.)"""
    http_app = getattr(mcp, "http_app", None)
    if http_app is not None:
        return http_app(stateless_http=True)
    sse_app = getattr(mcp, "sse_app", None)
    if sse_app is None:
        raise RuntimeError("Installed fastmcp exposes neither http_app() nor sse_app()")
    return sse_app()


def get_asgi_app(raw_app=None):
    """Return the FastMCP ASGI app wrapped with auth middleware.
    Pass raw_app if you need to share the same instance used for lifespan."""
    if raw_app is None:
        raw_app = get_raw_mcp_app()
    return ServiceTokenMiddleware(raw_app)


async def agent_broadcast(workspace_id: str, tool_name: str, status: str, summary: str = ""):
    """
    Broadcast agent tool activity to workspace WebSocket clients.
    Import this in each tool module:
        from mcp_server.server import agent_broadcast

    status: "running" | "done" | "error"
    Never raises — broadcast failures must not break tool calls.
    """
    try:
        from ws.manager import broadcast_agent_event
        await broadcast_agent_event(
            workspace_id,
            "tool_call",
            {
                "tool": tool_name,
                "status": status,
                "summary": summary[:200] if summary else "",
            },
        )
    except Exception:
        pass  # Never let broadcast failure break a tool call
