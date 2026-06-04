from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, workspaces, channels, messages, tasks, projects, files, notifications, documents, task_comments, dms, threads, ai_routes, search, ai_agents, users, proposed_actions, hermes_chat, hermes_teams, integrations, finance, seo, github_webhook, invites, intelligence, openrouter_models, boardroom
from ws.manager import router as ws_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# Build MCP ASGI app early so its lifespan can be wired into FastAPI.
# fastmcp requires the raw app's lifespan to be in the parent app's lifespan context.
# We keep a reference to the raw app for lifespan, and mount the auth-wrapped version.
from mcp_server.server import get_raw_mcp_app, get_asgi_app as _get_mcp_asgi, register_mcp_tools

register_mcp_tools()
_raw_mcp_app = get_raw_mcp_app()
_mcp_asgi_app = _get_mcp_asgi(raw_app=_raw_mcp_app)  # same raw_app, auth-wrapped

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Combined lifespan: APScheduler + fastmcp StreamableHTTP session manager."""
    # Start APScheduler
    from routers.ai_agents import _run_all_workspace_digests
    scheduler.add_job(
        _run_all_workspace_digests,
        CronTrigger(hour=8, minute=0),  # 8 AM UTC daily
        id="daily_digest",
        replace_existing=True,
    )
    # Auto-approve low/medium-risk agent proposed actions (high-risk deletes stay
    # gated). Multi-worker safe via FOR UPDATE SKIP LOCKED in the sweeper itself.
    from core.auto_approve import auto_approve_pending_actions
    scheduler.add_job(
        auto_approve_pending_actions,
        IntervalTrigger(seconds=5),
        id="auto_approve_actions",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    # Initialize fastmcp's session manager via its lifespan context manager.
    # _raw_mcp_app is a StarletteWithLifespan; its .lifespan is an ASGI lifespan.
    async with _raw_mcp_app.router.lifespan_context(app):
        yield

    scheduler.shutdown()


app = FastAPI(title="Loop API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(channels.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(task_comments.router, prefix="/api/v1")
app.include_router(dms.router, prefix="/api/v1")
app.include_router(threads.router, prefix="/api/v1")
app.include_router(ai_routes.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(ai_agents.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(proposed_actions.router, prefix="/api/v1")
app.include_router(hermes_chat.router)
app.include_router(hermes_teams.router)
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(finance.router, prefix="/api/v1")
app.include_router(seo.router, prefix="/api/v1")
app.include_router(github_webhook.router, prefix="/api/v1")
app.include_router(github_webhook.router, prefix="/api")   # serves /api/github/webhook (ngrok URL)
app.include_router(invites.router, prefix="/api/v1")
app.include_router(openrouter_models.router, prefix="/api/v1")
app.include_router(intelligence.router)
app.include_router(boardroom.router, prefix="/api/v1")
app.include_router(ws_router)

# Mount Hermes MCP server at /mcp (auth-wrapped)
# Hermes connects to http://<host>:8000/mcp with Authorization: Bearer <token>
app.mount("/mcp", _mcp_asgi_app)


@app.get("/health")
async def health():
    return {"status": "ok"}
