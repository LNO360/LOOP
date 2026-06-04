# Loop — Open-Source AI Workspace OS

> A self-hosted workspace platform for small teams, with a built-in AI agent (Hermes) that connects to your tasks, calendar, email, GitHub, and finances — reachable via Telegram or the web UI.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](docker-compose.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](apps/api)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs)](apps/web)

---

## Table of Contents

- [What is Loop?](#what-is-loop)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start — Local Development](#quick-start--local-development)
- [Environment Variables](#environment-variables)
- [Production Deployment](#production-deployment)
- [Hermes AI Agent](#hermes-ai-agent)
- [Integrations](#integrations)
- [Adding Skills to Hermes](#adding-skills-to-hermes)
- [Database Migrations](#database-migrations)
- [Backups](#backups)
- [Upgrading](#upgrading)
- [Development Guide](#development-guide)
- [Contributing](#contributing)
- [License](#license)

---

## What is Loop?

Loop is a full-stack, self-hosted workspace OS built for small teams who want to own their data. It replaces the fragmented combination of Notion + Linear + Slack + a generic AI assistant with a single platform you deploy and control.

The core differentiator is **Hermes** — an autonomous AI agent sidecar that connects to every part of your workspace via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Hermes can read your open tasks, upcoming calendar events, unread emails, and recent GitHub activity, and act on them — proactively, on a schedule, or on demand from Telegram.

---

## Features

### Task & Project Management
- Kanban boards with drag-and-drop columns
- Projects with descriptions, owners, and status
- Tasks with assignees, due dates, priorities, labels, and subtasks
- Task comments and activity history

### Team Chat
- Channels (public/private) with threaded replies
- Direct messages
- Reactions, pinning, and message search
- Real-time delivery via WebSocket (Redis pub/sub fan-out)

### Docs
- Collaborative markdown documents scoped to workspaces
- Rich editing with live save

### AI Agent (Hermes)
- Claude / OpenRouter-powered agent connected to all workspace data via MCP
- Reachable via Telegram bot or built-in web chat UI
- Runs scheduled jobs (daily digest, memory gardening, etc.)
- Semantic workspace memory backed by pgvector
- Extensible via plain-text skill files
- Parallel subagent delegation for complex multi-step tasks

### Finance Tracking
- Manual income and expense ledger with categorisation
- Summary views and reporting via Hermes

### Blog CMS
- Markdown blog with slug management and SEO metadata
- SEO audit tools connected to Google Search Console
- Optionally paired with a separate Vercel/Supabase marketing site

### Integrations
- **Google Calendar** — read events, create meetings
- **Gmail** — read and draft emails
- **Google Drive** — browse and fetch files
- **Google Search Console** — search analytics, URL inspection, sitemap management
- **GitHub** — repository data, issues, PRs, webhook events (GitHub App)

---

## Architecture

```
Browser / Telegram
       │
       ▼
 ┌─────────────┐     REST / WS      ┌──────────────────────────────┐
 │  Next.js 15  │ ◄────────────────► │  FastAPI  (api:8000)          │
 │   (web:3000) │                    │  ├─ REST  /api/v1/…           │
 └─────────────┘                    │  ├─ WS    /ws/{workspace_id}  │
                                    │  └─ MCP   /mcp/mcp            │
                                    └────────────┬─────────────────┘
                                                 │ MCP (HTTP)
                                    ┌────────────▼─────────────────┐
                                    │  Hermes agent (hermes:9119)   │
                                    │  ├─ Telegram gateway          │
                                    │  ├─ Web chat gateway          │
                                    │  └─ Cron scheduler            │
                                    └──────────────────────────────┘

Infrastructure
  PostgreSQL + pgvector  ←  primary database + semantic search
  Redis                  ←  WebSocket pub/sub + caching
  MinIO                  ←  S3-compatible file storage
  SearXNG                ←  private web search (no API key required)
  Caddy                  ←  reverse proxy + automatic TLS (production)
```

**Data flow examples:**

| Trigger | Path |
|---|---|
| User creates a task in the browser | Browser → Next.js → FastAPI REST → PostgreSQL |
| Hermes sends a channel message | Hermes → MCP tool → FastAPI → Redis pub/sub → WebSocket → Next.js |
| Telegram message arrives | Telegram → Hermes gateway → MCP tools → FastAPI → PostgreSQL |
| Scheduled digest | Cron → Hermes → MCP tools → `lno_send_channel_message` → WS → Next.js |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Better Auth |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16 + pgvector |
| Cache / PubSub | Redis 7 |
| File storage | MinIO (S3-compatible) |
| AI agent | Hermes CLI, OpenRouter / Claude, MCP protocol |
| Web search | SearXNG (self-hosted, no API key) |
| Infrastructure | Docker Compose, Caddy 2, GitHub Actions |

---

## Prerequisites

**All environments:**
- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/install/) v2 (`docker compose`, not `docker-compose`)
- Git

**Production only:**
- A Linux VPS or bare-metal server with at least **2 GB RAM** (4 GB recommended if running Hermes)
- A domain name with an A record pointing to your server's IP
- Ports 80 and 443 open in your firewall

**Optional (for full functionality):**
- Telegram Bot token (for the Hermes Telegram gateway)
- OpenRouter API key (for Hermes AI — free tier available)
- Google OAuth credentials (for Calendar, Gmail, Drive, Search Console integrations)
- GitHub App credentials (for GitHub integration)

---

## Quick Start — Local Development

```bash
# 1. Clone the repository
git clone https://github.com/LNO360/LOOP.git
cd LOOP

# 2. Copy the development environment file
cp .env.example .env

# 3. Edit .env — the minimum required values are pre-filled for local dev.
#    Review and adjust if needed (see Environment Variables below).
nano .env

# 4. Start all services
docker compose up -d

# 5. Run database migrations
docker compose exec api alembic upgrade head

# 6. Open the app
open http://localhost:3000
```

**Local service URLs:**

| Service | URL |
|---|---|
| Web UI | http://localhost:3000 |
| API (FastAPI docs) | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |
| SearXNG | http://localhost:8080 |

To watch logs across all services:
```bash
docker compose logs -f
```

To stop everything:
```bash
docker compose down
```

---

## Environment Variables

Copy `.env.example` (development) or `.env.prod.example` (production) and fill in the values. Every variable has an inline comment in those files — this table is a summary.

### Core

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string, e.g. `postgresql+asyncpg://lno:password@postgres:5432/lno_os` |
| `SYNC_DATABASE_URL` | Yes | Same host/db but with `postgresql://` (used by Alembic) |
| `REDIS_URL` | Yes | Redis connection string, e.g. `redis://redis:6379` |
| `BETTER_AUTH_SECRET` | Yes | Random 32-char secret for session signing. Generate: `openssl rand -hex 32` |
| `BETTER_AUTH_URL` | Yes | Your app's public URL, e.g. `https://yourdomain.com` |
| `NEXT_PUBLIC_API_URL` | Yes | Public API URL, e.g. `https://yourdomain.com` |
| `NEXT_PUBLIC_WS_URL` | Yes | Public WebSocket URL, e.g. `wss://yourdomain.com` |

### File Storage (MinIO / S3)

| Variable | Required | Description |
|---|---|---|
| `S3_ENDPOINT_URL` | Yes | MinIO endpoint, e.g. `http://minio:9000` |
| `S3_ACCESS_KEY` | Yes | MinIO root user |
| `S3_SECRET_KEY` | Yes | MinIO root password |
| `S3_BUCKET_NAME` | Yes | Bucket name (created automatically on first run) |
| `S3_REGION` | No | Region string (default: `us-east-1`) |

### Security

| Variable | Required | Description |
|---|---|---|
| `INTEGRATION_ENCRYPTION_KEY` | Yes | Fernet key for encrypting OAuth tokens at rest. Generate: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Hermes AI Agent

| Variable | Required | Description |
|---|---|---|
| `HERMES_SERVICE_TOKEN` | Yes | Shared token between API and Hermes. Generate: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `OPENROUTER_API_KEY` | For Hermes | OpenRouter API key (primary). Free tier works. |
| `OPENROUTER_API_KEY_SECONDARY` | No | Second OpenRouter key for fallback quota |
| `GROQ_API_KEY` | No | Groq API key as a third fallback |

### Telegram (optional)

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | No | From [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_ALLOWED_USERS` | No | Comma-separated numeric Telegram user IDs allowed to message Hermes |
| `TELEGRAM_BOT_NAME` | No | Your bot's @username (without the `@`) |

### Google Integrations (optional)

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_CLIENT_ID` | No | OAuth 2.0 client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | No | OAuth 2.0 client secret |

### GitHub Integration (optional)

| Variable | Required | Description |
|---|---|---|
| `GITHUB_APP_ID` | No | GitHub App ID (from app settings page) |
| `GITHUB_APP_NAME` | No | GitHub App slug name |
| `LNO_SECRETS_DIR` | No | Path to directory containing `github-app.private-key.pem` (default: `~/.lno-secrets`) |

### Production extras

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_USER` | Prod | PostgreSQL user |
| `POSTGRES_PASSWORD` | Prod | PostgreSQL password (use a strong random value) |
| `POSTGRES_DB` | Prod | Database name |
| `HERMES_CONTAINER` | No | Docker container name of the Hermes service (default: `lno-os-hermes-1`) |
| `DOCKER_GID` | No | Host Docker socket GID — needed for `docker exec` from API workers. Get with: `stat -c '%g' /var/run/docker.sock` |
| `DEFAULT_WORKSPACE_ID` | No | UUID of the primary workspace (used by Hermes scheduled digest) |
| `DIGEST_WORKSPACE_IDS` | No | Comma-separated workspace IDs for the morning digest cron |

---

## Production Deployment

### 1. Provision a server

Any Linux VPS works. Tested on Ubuntu 22.04. Minimum specs:
- 2 GB RAM (4 GB if running Hermes with browser toolset)
- 20 GB disk
- Ports 80, 443, and 22 open

Install Docker:
```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Clone the repository

```bash
git clone https://github.com/LNO360/LOOP.git /opt/loop
cd /opt/loop
```

### 3. Configure environment variables

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

Every variable has an inline comment. At minimum, set:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- `BETTER_AUTH_SECRET` (random 32-char hex)
- `BETTER_AUTH_URL`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL` (your domain)
- `S3_ACCESS_KEY`, `S3_SECRET_KEY`
- `INTEGRATION_ENCRYPTION_KEY` (Fernet key)
- `HERMES_SERVICE_TOKEN` (random 32-char hex)
- `OPENROUTER_API_KEY` (for Hermes)

### 4. Configure Caddy (HTTPS)

Edit `Caddyfile` and replace the placeholders:

```caddyfile
{
    email your@email.com   # real email — used for Let's Encrypt cert notices
}

yourdomain.com {
    @backend path /api/* /ws/*
    reverse_proxy @backend api:8000

    reverse_proxy web:3000

    encode gzip zstd
}
```

Caddy fetches a free TLS certificate from Let's Encrypt automatically on first start. Your DNS A record must be pointing at the server before you deploy.

### 5. (Optional) Store secrets outside the repo

If using the GitHub integration, place the private key at `~/.lno-secrets/github-app.private-key.pem` on the server (never inside the repo tree). The `LNO_SECRETS_DIR` variable controls where Docker mounts it.

### 6. Deploy

```bash
bash deploy.sh
```

The `deploy.sh` script:
1. Pulls the latest code (`git pull`)
2. Creates a timestamped PostgreSQL backup to `/opt/lno-backups/` (retains last 7)
3. Builds Docker images for `api` and `web`
4. Runs Alembic migrations (`alembic upgrade head`)
5. Restarts all services via `docker compose --env-file .env.prod -f docker-compose.prod.yml up -d`
6. Runs an API health check

On subsequent deploys, just re-run `bash deploy.sh`.

### 7. CI/CD with GitHub Actions (optional)

The included workflow at `.github/workflows/deploy.yml` triggers a Coolify deploy webhook on every push to `main`. Add these secrets to your GitHub repository:

| Secret | Value |
|---|---|
| `COOLIFY_WEBHOOK_URL` | Your Coolify deploy webhook URL |
| `COOLIFY_WEBHOOK_TOKEN` | The webhook token |

If you're not using Coolify, you can adapt the workflow to SSH into your server and run `deploy.sh` directly.

---

## Hermes AI Agent

Hermes is the AI brain of Loop. It runs as a separate Docker container alongside the API, connects to it via MCP, and can read and write everything in your workspace.

### How it works

1. The Loop API exposes an MCP server at `/mcp/mcp`
2. Hermes authenticates with a shared `HERMES_SERVICE_TOKEN`
3. Users message Hermes via Telegram or the built-in web chat
4. Hermes invokes MCP tools to read/write tasks, memory, channels, integrations, etc.
5. Scheduled cron jobs run Hermes automatically (every 2 hours + morning digest)

### Choosing a model

Hermes uses [OpenRouter](https://openrouter.ai) by default, which gives access to hundreds of models including free-tier options. Edit `hermes/config.yaml` to change the model:

```yaml
model:
  default: "openrouter/owl-alpha"   # change to any OpenRouter model ID
  provider: "openrouter"
```

Popular choices:
- `openrouter/owl-alpha` — fast, free tier available
- `anthropic/claude-opus-4-8` — most capable (paid)
- `anthropic/claude-sonnet-4-6` — strong balance of capability and cost (paid)
- `deepseek/deepseek-v4-flash` — fast and cheap

You can also configure Claude directly (without OpenRouter) by adding the Anthropic provider:

```yaml
providers:
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"

model:
  default: "claude-sonnet-4-6"
  provider: "anthropic"
```

### Fallback providers

Hermes supports automatic fallback when the primary model hits rate limits:

```yaml
fallback_providers:
  - provider: custom:openrouter2
    model: openrouter/free
  - provider: custom:groq
    model: llama-3.3-70b-versatile
```

### Available toolsets

Toolsets are enabled in `hermes/config.yaml` under `toolsets:`. Each toolset adds a set of capabilities:

| Toolset | What it enables |
|---|---|
| `hermes-cli` | File system access, memory read/write, terminal commands |
| `mcp` | All Loop workspace tools (tasks, channels, memory, integrations) |
| `skills` | Reads skill files from `apps/hermes-skills/` and `apps/user-agent-skills/` |
| `web` | Web search (via SearXNG) and page fetching |
| `delegation` | Spawn parallel subagents for multi-step tasks |
| `session_search` | Search past conversation history |
| `todo` | Multi-step planning within a single turn |
| `cronjob` | Create and edit scheduled jobs from chat |
| `vision` | Analyse images and screenshots sent via Telegram |
| `code_execution` | Run sandboxed Python scripts for data processing |
| `clarify` | Ask the user for clarification when a request is ambiguous |
| `browser` | Headless Chromium for JS-heavy websites |

### Telegram setup

1. Create a bot via [@BotFather](https://t.me/BotFather) → get a bot token
2. Get your numeric Telegram user ID (message [@userinfobot](https://t.me/userinfobot))
3. Set in `.env` / `.env.prod`:
   ```bash
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   TELEGRAM_ALLOWED_USERS=123456789   # your numeric ID
   TELEGRAM_BOT_NAME=your_bot_username
   ```
4. Restart Hermes: `docker compose restart hermes`
5. Send a message to your bot — it should respond within a few seconds

### Web chat

The built-in web chat is available in the Loop UI without any additional setup. It communicates with Hermes via the FastAPI `/hermes/chat` endpoint, which proxies to the Hermes dashboard HTTP API.

### Workspace memory

Hermes maintains a tiered memory system:

| Tier | Storage | When to use |
|---|---|---|
| Hot | `apps/hermes-data/memories/MEMORY.md` | Critical facts needed every session (≤ 6 KB) |
| Warm | PostgreSQL `workspace_memories` table | Everything else — searchable via `lno_search_workspace_memory` |
| Cold | Past chat sessions | Historical context — searchable via `session_search` |

You can ask Hermes to remember things directly: _"Remember that our sprint ends every Friday"_ and it will store that in the appropriate tier.

### Scheduled cron jobs

Ask Hermes to create a cron:

> "Every morning at 8am, check my tasks and send me a digest in #general"

Hermes creates a cron configuration and runs it using a lightweight, cost-optimised model profile (`hermes/profile-cron-config.yaml`). You can manage crons from Telegram or the web chat.

---

## Integrations

### Google (Calendar, Gmail, Drive, Search Console)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → **APIs & Services** → **Enable APIs**
   - Enable: Gmail API, Google Calendar API, Google Drive API, Google Search Console API
3. **OAuth consent screen** → configure with your domain and scopes:
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/drive.readonly`
   - `https://www.googleapis.com/auth/webmasters.readonly`
4. **Credentials** → Create OAuth 2.0 Client ID (type: Web application)
   - Authorised redirect URI: `https://yourdomain.com/api/v1/integrations/google/callback`
5. Set in `.env.prod`:
   ```bash
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_client_secret
   ```
6. In the Loop UI → **Settings** → **Integrations** → connect Google

### GitHub (GitHub App)

1. Go to **GitHub Settings** → **Developer settings** → **GitHub Apps** → **New GitHub App**
2. Set the webhook URL to `https://yourdomain.com/api/v1/github/webhook`
3. Grant the permissions your team needs (e.g. issues read/write, pull requests read)
4. Generate a private key and download the `.pem` file
5. Place the `.pem` file on your server at `~/.lno-secrets/github-app.private-key.pem`
6. Set in `.env.prod`:
   ```bash
   GITHUB_APP_ID=123456
   GITHUB_APP_NAME=your-app-slug
   LNO_SECRETS_DIR=/root/.lno-secrets
   ```

### Telegram

See [Hermes — Telegram setup](#telegram-setup) above.

---

## Adding Skills to Hermes

Skills are plain-text markdown files that give Hermes new workflows. Drop a `.md` file in `apps/hermes-skills/` — Hermes picks it up automatically (the directory is bind-mounted into the container).

**Example skill** (`apps/hermes-skills/weekly-review.md`):

```markdown
# Weekly Review

Run every Friday at 5pm. Summarise this week's completed tasks across all projects,
highlight anything overdue, and post the summary to #general.

## Steps
1. Call lno_list_tasks with status=done and filter to this week
2. Call lno_list_tasks with status=overdue
3. Format a markdown summary grouped by project
4. Call lno_send_channel_message to post it to #general
```

User-created skills (written from within the UI or by Hermes itself) are stored in `apps/user-agent-skills/` — a writable mount that persists across container restarts.

See `apps/hermes-skills/` for the included example skills.

---

## Database Migrations

Loop uses [Alembic](https://alembic.sqlalchemy.org/) for schema migrations.

**Run pending migrations** (done automatically by `deploy.sh` in production):
```bash
docker compose exec api alembic upgrade head
```

**Check current migration state:**
```bash
docker compose exec api alembic current
```

**Create a new migration after changing a SQLAlchemy model:**
```bash
docker compose exec api alembic revision --autogenerate -m "add widget table"
```

Review the generated file in `apps/api/alembic/versions/` before applying it.

**Roll back one migration:**
```bash
docker compose exec api alembic downgrade -1
```

---

## Backups

### PostgreSQL

`deploy.sh` automatically creates a compressed backup to `/opt/lno-backups/` before every deploy and retains the last 7 backups.

Manual backup:
```bash
docker compose exec postgres pg_dump -U lno lno_os | gzip > backup-$(date +%Y%m%d).sql.gz
```

Restore:
```bash
gunzip -c backup-20260101.sql.gz | docker compose exec -T postgres psql -U lno lno_os
```

### Hermes memory and knowledge

Hermes memory files live in the `hermes-data` Docker volume and in the bind-mounted `apps/hermes-data/` directory.

Back up the volume:
```bash
docker run --rm \
  -v lnoos_hermes-data:/data \
  -v /opt/lno-backups:/out \
  alpine tar czf /out/hermes-data-$(date +%Y%m%d).tar.gz -C /data .
```

Or use the included backup script to sync Hermes data to the host:
```bash
pnpm backup:hermes         # sync memory + knowledge files
pnpm backup:hermes:full    # sync + include database backup
```

### MinIO (file storage)

Use the [MinIO Client (`mc`)](https://min.io/docs/minio/linux/reference/minio-mc.html) to mirror your bucket:
```bash
mc alias set loop http://localhost:9000 your_access_key your_secret_key
mc mirror loop/your-bucket /opt/lno-backups/minio/
```

---

## Upgrading

```bash
cd /opt/loop

# Pull latest changes
git pull

# Deploy (builds images, runs migrations, restarts services)
bash deploy.sh
```

The deploy script handles migrations automatically. Check the release notes for any manual steps before upgrading major versions.

---

## Development Guide

### Running services individually

**API only** (with hot-reload):
```bash
docker compose up -d postgres redis minio searxng
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../../.env .env
uvicorn main:app --reload --port 8000
```

**Frontend only:**
```bash
pnpm install
pnpm dev:web
```

**Both** (Docker Compose dev mode includes all services):
```bash
docker compose up -d
```

### Useful scripts

```bash
pnpm dev:web                    # start Next.js dev server
pnpm dev:api                    # start FastAPI with hot-reload (uvicorn)
pnpm db:migrate                 # run alembic upgrade head
pnpm db:makemigration "message" # create a new migration
pnpm backup:hermes              # sync Hermes memory/knowledge to host
pnpm cleanup:workspaces         # list stale workspaces
pnpm cleanup:workspaces:dry     # dry-run stale workspace cleanup
```

### Project structure

```
Loop/
├── apps/
│   ├── api/                  # FastAPI backend
│   │   ├── routers/          # Route handlers (tasks, channels, auth, …)
│   │   ├── models/           # SQLAlchemy models
│   │   ├── services/         # Business logic
│   │   ├── mcp_server/       # MCP server exposed to Hermes
│   │   ├── agents/           # AI agent runners
│   │   └── alembic/          # Database migrations
│   ├── web/                  # Next.js 15 frontend
│   │   └── src/
│   │       ├── app/          # App Router pages
│   │       ├── components/   # React components
│   │       ├── hooks/        # Custom hooks
│   │       ├── lib/          # API client, utilities
│   │       └── store/        # Zustand state
│   ├── hermes-skills/        # Built-in Hermes skill files (read-only mount)
│   ├── user-agent-skills/    # User-created skill files (writable mount)
│   └── hermes-data/          # Hermes memory files (bind-mounted)
│       ├── memories/
│       │   ├── MEMORY.md     # Hot memory (loaded every session)
│       │   └── USER.md       # User profile memory
│       └── knowledge/        # Long-form reference documents
├── hermes/                   # Hermes container build context
│   ├── Dockerfile
│   ├── config.yaml           # Hermes agent configuration
│   ├── SOUL.md               # Hermes system prompt / personality
│   └── profile-cron-config.yaml  # Lightweight config for scheduled runs
├── packages/
│   └── shared/               # Shared TypeScript types
├── infra/
│   └── searxng/              # SearXNG configuration
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── HERMES.md
├── docker-compose.yml        # Development compose file
├── docker-compose.prod.yml   # Production compose file
├── Caddyfile                 # Caddy reverse proxy config
├── deploy.sh                 # Production deploy script
└── .env.example              # Development environment template
```

### Running tests

```bash
# API tests (pytest)
docker compose exec api pytest

# Or locally with the venv active:
cd apps/api && pytest
```

---

## Contributing

Contributions are welcome. Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes and add tests where applicable
4. Open a pull request against `main`

For significant changes, open an issue first to discuss the approach.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — detailed system components and data flow
- [Deployment](docs/DEPLOYMENT.md) — step-by-step deployment reference
- [Hermes agent](docs/HERMES.md) — Hermes configuration, skills, and toolsets
