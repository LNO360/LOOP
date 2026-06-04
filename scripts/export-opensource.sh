#!/bin/bash
# LNO OS — Open Source Export Script
# Produces a clean public snapshot at ~/lno-os-public/
# Safe to re-run: wipes and recreates output from scratch. Private repo untouched.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$HOME/lno-os-public"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  LNO OS — Open Source Export"
echo "  Source : $REPO_DIR"
echo "  Output : $OUT_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. rsync ────────────────────────────────────────────────────────────────
rsync_tree() {
  echo "→ Copying working tree (rsync)..."
  rm -rf "$OUT_DIR"
  mkdir -p "$OUT_DIR"
  rsync -a \
    --exclude='.git/' \
    --exclude='node_modules/' \
    --exclude='.next/' \
    --exclude='dist/' \
    --exclude='build/' \
    --exclude='.venv/' \
    --exclude='venv/' \
    --exclude='backups/' \
    --exclude='*.pem' \
    --exclude='*.key' \
    --exclude='*.p12' \
    --exclude='.env' \
    --exclude='.env.prod' \
    --exclude='.env.local' \
    --exclude='.env.*.local' \
    --exclude='apps/hermes-data/' \
    --exclude='apps/hermes-skills/' \
    --exclude='apps/user-agent-skills/' \
    --exclude='docs/superpowers/' \
    --exclude='docs/qa/' \
    --exclude='Cream Black Typography Loop Brand Logo.svg' \
    --exclude='apps/api/.venv/' \
    --exclude='apps/api/__pycache__/' \
    --exclude='apps/api/*.egg-info/' \
    --exclude='apps/api/.pytest_cache/' \
    --exclude='apps/api/.mypy_cache/' \
    --exclude='apps/api/.ruff_cache/' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='apps/web/.next/' \
    --exclude='apps/web/node_modules/' \
    "$REPO_DIR/" "$OUT_DIR/"
  echo "   ✓ rsync complete"
}

# ── 2. Patch env files ──────────────────────────────────────────────────────
patch_env_files() {
  echo "→ Patching env files..."
  # .env.example: remove production workspace UUID
  sed -i '' \
    's/^DIGEST_WORKSPACE_IDS=.*/DIGEST_WORKSPACE_IDS=/' \
    "$OUT_DIR/.env.example"
  # .env.prod.example: replace real Groq key with placeholder
  sed -i '' \
    's/^GROQ_API_KEY=gsk_.*/GROQ_API_KEY=your_groq_api_key_here/' \
    "$OUT_DIR/.env.prod.example"
  # .env.prod.example: replace LNO-specific Telegram bot name
  sed -i '' \
    's/^TELEGRAM_BOT_NAME=LNO_Founders_office_bot/TELEGRAM_BOT_NAME=your_telegram_bot_name/' \
    "$OUT_DIR/.env.prod.example"
  # .env.prod.example: replace internal GitHub site repo reference
  sed -i '' \
    's|^LNO_SITE_GITHUB_REPO=LNO360/lnotechnology|LNO_SITE_GITHUB_REPO=your-org/your-site-repo|' \
    "$OUT_DIR/.env.prod.example"
  echo "   ✓ env files patched"
}

# ── 3. Patch config.py ──────────────────────────────────────────────────────
patch_config_py() {
  echo "→ Patching apps/api/core/config.py..."
  CONFIG="$OUT_DIR/apps/api/core/config.py"
  # Remove hardcoded production workspace UUID default
  sed -i '' \
    's/digest_workspace_ids: str = "ac153f45-27ad-49f8-9813-83258db7f674"/digest_workspace_ids: str = ""/' \
    "$CONFIG"
  # Remove hardcoded internal Telegram bot name default
  sed -i '' \
    's/telegram_bot_name: str = "LNO_Founders_office_bot"/telegram_bot_name: str = ""/' \
    "$CONFIG"
  # Remove hardcoded internal GitHub repo default
  sed -i '' \
    's|lno_site_github_repo: str = "LNO360/lnotechnology"|lno_site_github_repo: str = ""|' \
    "$CONFIG"
  # Clean up inline comment referencing the internal repo URL
  sed -i '' \
    's|  # https://github.com/LNO360/lnotechnology||' \
    "$CONFIG"
  # Remove comment referencing LNO360 org name
  sed -i '' \
    's|# When set, GitHub MCP tools only access this org (e.g. LNO360), not personal repos|# When set, GitHub MCP tools only access this org, not personal repos|' \
    "$CONFIG"
  # Remove @LNO_Founders_office_bot from Telegram comment
  sed -i '' \
    's|# Telegram (@LNO_Founders_office_bot) — notify + approve via Hermes chat|# Telegram — notify + approve via Hermes chat|' \
    "$CONFIG"
  echo "   ✓ config.py patched"
}

# ── 4a. Patch hermes/config.yaml comments ───────────────────────────────────
patch_hermes_config() {
  echo "→ Patching hermes/config.yaml..."
  HCONFIG="$OUT_DIR/hermes/config.yaml"
  # Remove bot name from comment
  sed -i '' \
    's|# Bot: @LNO_Founders_office_bot|# Bot: @your_telegram_bot_name|' \
    "$HCONFIG"
  echo "   ✓ hermes/config.yaml patched"
}

# ── 4b. Patch Caddyfile ─────────────────────────────────────────────────────
patch_caddyfile() {
  echo "→ Patching Caddyfile..."
  # Replace internal email
  sed -i '' \
    's|email you@lno.co.in|email you@example.com|' \
    "$OUT_DIR/Caddyfile"
  # Replace internal domain with generic placeholder
  sed -i '' \
    's|loop.lno.co.in {|your-domain.com {|' \
    "$OUT_DIR/Caddyfile"
  echo "   ✓ Caddyfile patched"
}

# ── 5. Hermes-data placeholder dirs ────────────────────────────────────────
create_hermes_data_placeholders() {
  echo "→ Creating hermes-data placeholder structure..."
  mkdir -p "$OUT_DIR/apps/hermes-data/memories"
  mkdir -p "$OUT_DIR/apps/hermes-data/knowledge"
  touch "$OUT_DIR/apps/hermes-data/memories/.gitkeep"
  touch "$OUT_DIR/apps/hermes-data/knowledge/.gitkeep"
  echo "   ✓ hermes-data placeholders created"
}

# ── 6. Example skills ───────────────────────────────────────────────────────
write_example_skills() {
  echo "→ Writing example skills..."
  mkdir -p "$OUT_DIR/apps/hermes-skills"
  mkdir -p "$OUT_DIR/apps/user-agent-skills/example-researcher"

  cat > "$OUT_DIR/apps/hermes-skills/example-daily-digest.md" << 'SKILL'
# Daily Digest — Example Hermes Skill

Sends a morning summary of tasks due today, overdue items, and workspace activity.

## When to use

Trigger manually ("give me the daily digest") or schedule as a cron job:
> "Every morning at 8am, run the daily digest"

## Steps

1. Fetch today's tasks: `lno_list_tasks` with `due_today=true`
2. Fetch overdue items: `lno_list_overdue_tasks`
3. Fetch workspace snapshot: `lno_get_workspace_snapshot`
4. Format as a concise summary (< 400 chars for Telegram)
5. Send via `lno_send_channel_message` to your preferred channel

## Example output

> 📋 **Daily Digest — Jun 4**
> ✅ 3 tasks due today
> ⚠️ 2 overdue (review needed)
> 💬 5 new channel messages

## Customising

- Change the target channel by passing a different `channel_id`
- Add finance summary using the finance MCP tools
- Filter by assignee for personalised digests
SKILL

  cat > "$OUT_DIR/apps/hermes-skills/example-memory-gardener.md" << 'SKILL'
# Memory Gardener — Example Hermes Skill

Periodically reviews and prunes workspace memory to keep it accurate and relevant.

## When to use

Run weekly ("tidy up the workspace memory") or after major project changes.

## Steps

1. Retrieve all entries: `lno_get_workspace_memory`
2. Identify stale entries (outdated project status, superseded decisions, old facts)
3. For each stale entry, confirm it is no longer valid
4. Delete confirmed stale entries: `lno_delete_workspace_memory`
5. Update entries that need correction: `lno_upsert_workspace_memory`

## Guidelines

- Keep entries under 200 characters each
- Remove duplicates of information already in tasks or projects
- Preserve rationale and decisions even if the outcome changed
- Merge related entries to reduce total count
SKILL

  cat > "$OUT_DIR/apps/user-agent-skills/example-researcher/SKILL.md" << 'SKILL'
# Researcher — Example User Agent Skill

Conducts thorough web research on a given topic and synthesises findings.

## When to use

"Research [topic] and summarise" or "Investigate [question] and save key facts to memory"

## Steps

1. Search for recent information: `web_search` with the topic as query
2. Read top 3–5 pages: `web_fetch_page` for each URL
3. Synthesise findings into a structured report with sources
4. If instructed, save key facts: `lno_upsert_workspace_memory`

## Output format

- **Summary** (2–3 sentences)
- **Key findings** (bullet list)
- **Sources** (URLs)
- **Saved to memory** (if applicable)

## Customising

Copy this file to `apps/user-agent-skills/<your-skill-name>/SKILL.md`
and adapt the steps and output format for your use case.
SKILL

  echo "   ✓ example skills written"
}

# ── 7. Replace company_context.py with generic example ─────────────────────
replace_company_context() {
  echo "→ Replacing company_context.py with generic example..."
  cat > "$OUT_DIR/apps/api/agents/company_context.py" << 'PYEOF'
"""
Company context injected into AI agent system prompts.
Edit this file to describe your organisation, products, and team.
"""

COMPANY_CONTEXT = """
## Your Company — Company Context

### Who We Are
[Your company name and one-line description.]
Products: [Product A], [Product B].
Positioning: "[Your positioning statement]"

### Products
- [Product A] — [Brief description. Key features: ...]
- [Product B] — [Brief description.]

### Team
- [Name] — [Role]. [email@example.com]
- [Name] — [Role]. [email@example.com]

### Key Metrics
- [Metric 1]: [value]
- [Metric 2]: [value]
"""
PYEOF
  echo "   ✓ company_context.py replaced"
}

# ── 8. README ───────────────────────────────────────────────────────────────
write_readme() {
  echo "→ Writing README.md..."
  cat > "$OUT_DIR/README.md" << 'README'
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
README
  echo "   ✓ README.md written"
}

# ── 9. LICENSE ──────────────────────────────────────────────────────────────
write_license() {
  echo "→ Writing LICENSE (Apache 2.0)..."
  YEAR=$(date +%Y)
  cat > "$OUT_DIR/LICENSE" << LICENSE
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship made available under
      the License, as indicated by a copyright notice that is included in
      or attached to the work (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other
      transformations represent, as a whole, an original work of authorship.

      "Contribution" shall mean, as defined by the copyright owner, any
      work of authorship, including the original version of the Work and any
      modifications or additions to that Work or Derivative Works of the Work,
      that is intentionally submitted to the Licensor for inclusion in the Work
      by the copyright owner or by an individual or Legal Entity authorized to
      submit on behalf of the copyright owner.

      "Contributor" shall mean Licensor and any Legal Entity on behalf of
      whom a Contribution has been received by the Licensor and included
      within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by the combination of their Contributions
      with the Work to which such Contributions were submitted.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or Derivative
          Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file, You must include a
          readable copy of the attribution notices contained within such
          NOTICE file.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor.

   7. Disclaimer of Warranty. Unless required by applicable law or agreed
      to in writing, Licensor provides the Work on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any conditions of TITLE,
      NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR
      PURPOSE. You are solely responsible for determining the
      appropriateness of using or reproducing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      shall any Contributor be liable to You for damages, including any
      direct, indirect, special, incidental, or exemplary damages of any
      character arising as a result of this License or out of the use or
      inability to use the Work.

   9. Accepting Warranty or Liability. While redistributing the Work,
      You may offer, and charge a fee for, acceptance of support,
      warranty, indemnity, or other liability obligations and rights
      consistent with this License. However, in accepting such obligations,
      You may offer such obligations only on Your own behalf and on Your
      sole responsibility, not on behalf of any other Contributor.

   END OF TERMS AND CONDITIONS

   Copyright $YEAR LNO Technologies

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
LICENSE
  echo "   ✓ LICENSE written"
}

# ── 10. Docs ────────────────────────────────────────────────────────────────
write_docs() {
  echo "→ Writing docs..."
  mkdir -p "$OUT_DIR/docs"

  # Remove internal docs that will be overwritten or excluded
  rm -f "$OUT_DIR/docs/DEPLOYMENT.md"
  rm -f "$OUT_DIR/docs/MEMORY_EVOLUTION.md"
  rm -f "$OUT_DIR/docs/PLATFORM.md"
  rm -f "$OUT_DIR/docs/PRD.md"
  rm -f "$OUT_DIR/docs/PRODUCT.md"

  # ARCHITECTURE.md
  cat > "$OUT_DIR/docs/ARCHITECTURE.md" << 'DOC'
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
DOC

  # HERMES.md
  cat > "$OUT_DIR/docs/HERMES.md" << 'DOC'
# Hermes Agent

Hermes is the AI agent sidecar for LNO OS. It connects to your workspace via MCP and can be reached via Telegram or the built-in web chat.

## How it works

1. LNO OS API exposes an MCP server at `/mcp/mcp`
2. Hermes authenticates with a shared service token (`HERMES_SERVICE_TOKEN`)
3. Users send messages via Telegram or the web chat
4. Hermes uses MCP tools to read/write workspace data
5. It responds in the same channel

## Setup

### 1. Configure environment variables

Add to your `.env` / `.env.prod`:

```bash
# Generate: python3 -c "import secrets; print(secrets.token_hex(32))"
HERMES_SERVICE_TOKEN=your_32_char_hex_token_here

# Telegram (optional — from @BotFather)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USERS=your_numeric_telegram_user_id
TELEGRAM_BOT_NAME=your_bot_username

# AI model (OpenRouter recommended)
OPENROUTER_API_KEY=sk-or-...
```

### 2. Configure the agent

Edit `hermes/config.yaml` — set your preferred model, fallback providers, and toolsets. The config is mounted into the container at startup.

### 3. Start Hermes

```bash
docker compose up -d hermes
```

### 4. Test

Send a message to your Telegram bot, or open the Hermes web chat in the LNO OS UI.

## Adding skills

Skills are markdown files that give Hermes new workflows. Drop them in `apps/hermes-skills/` — they are mounted into the container automatically.

See `apps/hermes-skills/` for example skills.

## Scheduled tasks (crons)

Ask Hermes to create a cron job:

> "Every morning at 8am, check my tasks and send me a digest"

Crons run in a lightweight profile (`hermes/profile-cron-config.yaml`) using a free model tier to keep costs low.

## Toolsets

The toolsets loaded by Hermes are configured in `hermes/config.yaml` under `toolsets:`. Available options:

| Toolset | Description |
|---|---|
| `hermes-cli` | File system, memory, terminal |
| `mcp` | LNO OS workspace tools |
| `web` | Web search and page fetch |
| `skills` | Mounted skill files |
| `delegation` | Parallel subagents |
| `vision` | Image/screenshot analysis |
| `cronjob` | Create/edit scheduled jobs from chat |
| `browser` | Headless Chromium for JS-heavy sites |
| `code_execution` | Sandboxed script execution |
DOC

  # DEPLOYMENT.md
  cat > "$OUT_DIR/docs/DEPLOYMENT.md" << 'DOC'
# Deployment

## Prerequisites

- Docker and Docker Compose v2
- A server (VPS or bare metal) with 2 GB+ RAM
- A domain name with DNS pointed at your server
- (Optional) Telegram bot token for the Hermes agent

## Local development

```bash
cp .env.example .env
# Edit .env — minimum: DATABASE_URL, BETTER_AUTH_SECRET, S3_* keys
docker compose up -d
```

Services:
- Web UI: http://localhost:3000
- API: http://localhost:8000
- MinIO console: http://localhost:9001

## Production deployment

### 1. Prepare the server

```bash
git clone https://github.com/your-org/lno-os.git /opt/lno-os
cd /opt/lno-os

cp .env.prod.example .env.prod
nano .env.prod   # fill every value — see inline comments
```

### 2. Configure your domain

Edit `Caddyfile` — replace `your-domain.com` with your actual domain and set a real email for Let's Encrypt certificate notices.

### 3. Deploy

```bash
bash deploy.sh
```

The `deploy.sh` script:
1. Pulls the latest code (`git pull`)
2. Backs up PostgreSQL to `/opt/lno-backups/` (keeps last 7)
3. Builds Docker images (`api`, `web`)
4. Runs Alembic migrations
5. Restarts all services
6. Runs an API health check

### 4. CI/CD with GitHub Actions (optional)

The included workflow (`.github/workflows/deploy.yml`) triggers a Coolify deploy webhook on push to `main`.

Add these secrets to your GitHub repo:
- `COOLIFY_WEBHOOK_URL`
- `COOLIFY_WEBHOOK_TOKEN`

## Environment variables

`.env.example` — development defaults with inline documentation
`.env.prod.example` — production template with inline documentation

Every variable has a comment explaining what it is and how to generate it.

## Database migrations

```bash
# Run migrations manually
docker compose exec api alembic upgrade head

# Create a new migration
docker compose exec api alembic revision --autogenerate -m "description"
```

## Backups

PostgreSQL backups are written automatically by `deploy.sh` to `/opt/lno-backups/`.

Hermes memory and knowledge files live in the `hermes-data` Docker volume. Back it up with:

```bash
docker run --rm -v lnoos_hermes-data:/data -v /opt/lno-backups:/out \
  alpine tar czf /out/hermes-data-$(date +%Y%m%d).tar.gz -C /data .
```
DOC

  echo "   ✓ docs written"
}

# ── 11. Sanity check — warn on known sensitive patterns ─────────────────────
sanity_check() {
  echo "→ Running sanity check for sensitive patterns..."
  PATTERNS=(
    "gsk_[A-Za-z0-9]{40}"
    "ac153f45-27ad-49f8-9813-83258db7f674"
    "ashikjoy21@gmail.com"
    "verbiai210@gmail.com"
    "shaanshoukath4522"
    "LNO_Founders_office_bot"
    "LNO360/lnotechnology"
    "147\.93\."
  )
  FOUND=0
  for PATTERN in "${PATTERNS[@]}"; do
    HITS=$(grep -rn --include="*.py" --include="*.ts" --include="*.yaml" \
           --include="*.yml" --include="*.md" --include="*.sh" \
           --include="*.json" --include="*.env*" \
           -E "$PATTERN" "$OUT_DIR" 2>/dev/null || true)
    if [ -n "$HITS" ]; then
      echo "   ⚠️  SENSITIVE PATTERN FOUND: $PATTERN"
      echo "$HITS" | head -5
      FOUND=1
    fi
  done
  if [ "$FOUND" -eq 0 ]; then
    echo "   ✓ No known sensitive patterns found"
  else
    echo ""
    echo "   ⚠️  Review the matches above before pushing to a public repo."
    echo "      If they are false positives, proceed. Otherwise fix the script."
  fi
}

# ── 12. Git init ─────────────────────────────────────────────────────────────
git_init() {
  echo "→ Initialising git repo..."
  cd "$OUT_DIR"
  git init -b main
  git add .
  git commit -m "Initial open source release"
  echo "   ✓ Git repo initialised with single clean commit"
}

patch_docker_compose() {
  local dc="$OUT_DIR/docker-compose.prod.yml"
  local test_file="$OUT_DIR/apps/api/tests/test_lno_blog_tools.py"
  local cleanup_file="$OUT_DIR/apps/api/scripts/cleanup_workspaces.py"

  # Leak 1: remove hardcoded UUID default from DIGEST_WORKSPACE_IDS env fallback
  if [[ -f "$dc" ]]; then
    sed -i '' 's|${DIGEST_WORKSPACE_IDS:-ac153f45-27ad-49f8-9813-83258db7f674}|${DIGEST_WORKSPACE_IDS:-}|g' "$dc"
    echo "   ✓ Patched UUID default in docker-compose.prod.yml"
  fi

  # Leak 2: replace real workspace UUID used as test constant
  if [[ -f "$test_file" ]]; then
    sed -i '' 's|FAKE_WS_ID = "ac153f45-27ad-49f8-9813-83258db7f674"|FAKE_WS_ID = "00000000-0000-0000-0000-000000000000"|g' "$test_file"
    echo "   ✓ Patched FAKE_WS_ID in test_lno_blog_tools.py"
  fi

  # Leak 3: replace workspace UUID in cleanup_workspaces.py comment
  if [[ -f "$cleanup_file" ]]; then
    sed -i '' \
      's|Default keep: LNO Technologies (ac153f45-27ad-49f8-9813-83258db7f674)|Default keep: your-workspace-name (your-workspace-uuid)|' \
      "$cleanup_file"
    echo "   ✓ Patched comment in cleanup_workspaces.py"
  fi

  # Leak 4: replace workspace UUID in cleanup_workspaces.py constant
  if [[ -f "$cleanup_file" ]]; then
    sed -i '' \
      's|DEFAULT_KEEP_ID = "ac153f45-27ad-49f8-9813-83258db7f674"|DEFAULT_KEEP_ID = ""  # Set to your workspace UUID|' \
      "$cleanup_file"
    echo "   ✓ Patched DEFAULT_KEEP_ID in cleanup_workspaces.py"
  fi
}

# ── main ─────────────────────────────────────────────────────────────────────
main() {
  rsync_tree
  patch_env_files
  patch_config_py
  patch_hermes_config
  patch_caddyfile
  patch_docker_compose
  create_hermes_data_placeholders
  write_example_skills
  replace_company_context
  write_readme
  write_license
  write_docs
  sanity_check
  git_init

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  ✅  Export complete!"
  echo "  Output: $OUT_DIR"
  echo ""
  echo "  Next steps:"
  echo "  1. Create a new GitHub repo (e.g. github.com/new)"
  echo "  2. cd $OUT_DIR"
  echo "  3. git remote add origin https://github.com/YOUR-ORG/lno-os.git"
  echo "  4. git push -u origin main"
  echo ""
  echo "  ⚠️  Also rotate your Groq API key — it was previously"
  echo "      committed to git history in your private repo."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

main "$@"
