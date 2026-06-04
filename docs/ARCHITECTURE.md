# Architecture

## Overview

LNO OS is a monorepo with three main services: a Next.js frontend (`apps/web`), a FastAPI backend (`apps/api`), and a Hermes AI agent sidecar (`hermes/`). All services run in Docker containers orchestrated by Docker Compose.

## Services

### Web — `apps/web`
Next.js 15 frontend. Communicates with the API over REST (`/api/v1/`) and WebSocket (`/ws/{workspace_id}`). Authentication via Better Auth with sessions stored in PostgreSQL.

### API — `apps/api`
FastAPI application serving:
- REST endpoints under `/api/v1/`
- WebSocket at `/ws/{workspace_id}` (Redis pub/sub fan-out)
- MCP server at `/mcp/mcp` — FastMCP in `stateless_http=True` mode so it works behind a multi-worker uvicorn deployment
- Alembic for schema migrations
- APScheduler for background tasks (digest agent, memory extraction)

### Hermes — `hermes/`
AI agent sidecar running the Hermes CLI. Connects to the MCP server at `/mcp/mcp` via a shared service token (`HERMES_SERVICE_TOKEN`). Exposes a Telegram gateway and a web chat interface.

### Infrastructure
| Service | Purpose |
|---|---|
| PostgreSQL + pgvector | Primary database + semantic memory search |
| Redis | WebSocket pub/sub + caching |
| MinIO | File storage (S3-compatible) |
| SearXNG | Private web search for Hermes |
| Caddy | Reverse proxy + automatic TLS (production) |

## Data flow

```
User browser  → Next.js → FastAPI REST/WS → PostgreSQL / Redis / MinIO
Telegram msg  → Hermes  → MCP tools       → FastAPI → PostgreSQL
Cron job      → Hermes  → MCP tools       → lno_send_channel_message → WS → Next.js
```

## MCP server

`apps/api/mcp_server/` exposes workspace tools to Hermes:
- Task management — `lno_list_tasks`, `lno_create_task`, `lno_update_task`, …
- Memory — `lno_get_workspace_memory`, `lno_upsert_workspace_memory`, `lno_semantic_search_workspace_memory`, …
- Messaging — `lno_send_channel_message`, `lno_create_notification`
- Integrations — GitHub, Google (Calendar / Gmail / Drive / Search Console), finance, blog

Domain tools (Gmail, Drive, Calendar, GitHub, finance) are discoverable via `lno_find_tools` to keep the default toolset small.

## Auth

Better Auth manages sessions. The frontend and API share `BETTER_AUTH_SECRET`. OAuth integration tokens (Google, GitHub) are encrypted at rest with `INTEGRATION_ENCRYPTION_KEY` (Fernet).
