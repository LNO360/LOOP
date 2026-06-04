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
