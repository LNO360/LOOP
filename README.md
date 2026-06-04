# LNO OS

An open-source, self-hosted workspace OS for small teams — with an AI agent (Hermes) that reads your tasks, calendar, email, GitHub, and finances, and acts on them via Telegram or the web UI.

## What it is

LNO OS is a full-stack workspace platform combining:

- **Task & project management** — kanban boards, assignees, subtasks, comments
- **Team chat** — channels with threaded messages, reactions, pinning
- **AI agent (Hermes)** — a Claude/OpenRouter-powered agent connected to all your workspace data via MCP, reachable via Telegram or the web UI
- **Integrations** — Google Calendar, Gmail, Drive, GitHub, Search Console
- **Finance tracking** — manual income/expense ledger with categorisation
- **Blog CMS** — markdown blog with SEO tools, optionally connected to a Vercel/Supabase marketing site

## Architecture

```
Next.js (web) ←→ FastAPI (api) ←→ PostgreSQL + Redis + MinIO
                      ↕ MCP
              Hermes (AI agent sidecar)
                      ↕
            Telegram / Web chat gateway
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full breakdown.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Better Auth |
| Backend | FastAPI, Python 3.12, SQLAlchemy 2, Alembic |
| Storage | PostgreSQL + pgvector, Redis, MinIO |
| AI | Hermes agent, OpenRouter / Claude, MCP protocol |
| Infrastructure | Docker Compose, Caddy, GitHub Actions |

## Quick start

```bash
# 1. Clone
git clone https://github.com/your-org/lno-os.git
cd lno-os

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set DATABASE_URL, BETTER_AUTH_SECRET, and your S3 keys

# 3. Start
docker compose up -d

# 4. Open
open http://localhost:3000
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production setup with Caddy + TLS.

## Hermes AI agent

Hermes is an AI agent sidecar that connects to LNO OS via MCP and can:

- Read and create tasks, projects, and workspace memories
- Send messages to channels and Telegram notifications
- Access your integrations (GitHub, Google, finance)
- Run on a schedule via cron jobs
- Respond to Telegram messages in real time

See [docs/HERMES.md](docs/HERMES.md) for setup and how to extend it with custom skills.

## Extending with skills

Drop markdown skill files in `apps/hermes-skills/` to teach Hermes new workflows. Example skills are included — see the `apps/hermes-skills/` and `apps/user-agent-skills/` directories.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system components and data flow
- [Deployment](docs/DEPLOYMENT.md) — local dev and production setup
- [Hermes agent](docs/HERMES.md) — AI agent configuration and skills

## License

Apache 2.0 — see [LICENSE](LICENSE).
