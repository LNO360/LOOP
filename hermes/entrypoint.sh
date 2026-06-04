#!/bin/bash
# Hermes container entrypoint for LNO OS.
# Runs hermes gateway + dashboard in the foreground.

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Hermes Agent — LNO OS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
mkdir -p "$HERMES_HOME"

# Seed config/SOUL from image only on first boot (named volume).
# docker-compose bind-mounts ./hermes/config.yaml — do NOT overwrite on every start.
if [ -f /opt/lno-hermes/config.yaml ] && [ ! -f "$HERMES_HOME/config.yaml" ]; then
  cp /opt/lno-hermes/config.yaml "$HERMES_HOME/config.yaml"
fi
if [ -f /opt/lno-hermes/SOUL.md ] && [ ! -f "$HERMES_HOME/SOUL.md" ]; then
  cp /opt/lno-hermes/SOUL.md "$HERMES_HOME/SOUL.md"
fi

# ── Write .env file (Hermes reads this for API keys) ──────────
cat > "$HERMES_HOME/.env" <<EOF
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
HERMES_SERVICE_TOKEN=${HERMES_SERVICE_TOKEN:-dev-token-change-in-production}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS:-}
EOF
echo "→ .env written"

# ── Wait for LNO API to be healthy ────────────────────────────
echo "→ Waiting for API (http://api:8000/health)..."
ATTEMPTS=0
until curl -sf http://api:8000/health > /dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ $ATTEMPTS -ge 60 ]; then
    echo "✗ API did not become healthy after 5 minutes. Exiting."
    exit 1
  fi
  echo "  waiting... (${ATTEMPTS}/60)"
  sleep 5
done
echo "  ✓ API healthy"

# ── Default workspace for crons/Telegram (service token cannot call REST) ──
# Prefer DEFAULT_WORKSPACE_ID or first DIGEST_WORKSPACE_IDS from compose env / .env.prod.
echo "→ Setting default workspace for agent sessions..."
DEFAULT_WORKSPACE_ID="${DEFAULT_WORKSPACE_ID:-}"
if [ -z "$DEFAULT_WORKSPACE_ID" ] && [ -n "${DIGEST_WORKSPACE_IDS:-}" ]; then
  DEFAULT_WORKSPACE_ID=$(echo "$DIGEST_WORKSPACE_IDS" | cut -d, -f1 | tr -d ' ')
fi
if [ -n "$DEFAULT_WORKSPACE_ID" ]; then
  echo "  ✓ Default workspace: $DEFAULT_WORKSPACE_ID"
  echo "DEFAULT_WORKSPACE_ID=${DEFAULT_WORKSPACE_ID}" >> "$HERMES_HOME/.env"
else
  echo "  ✗ Set DEFAULT_WORKSPACE_ID or DIGEST_WORKSPACE_IDS in .env.prod"
fi

# ── Copy built-in skill files from volume mount ───────────────
if [ -d "/lno-skills" ] && [ "$(ls -A /lno-skills)" ]; then
  mkdir -p "$HERMES_HOME/skills/lno"
  cp -r /lno-skills/. "$HERMES_HOME/skills/lno/"
  echo "→ Built-in skills: $(ls $HERMES_HOME/skills/lno/ | wc -l) files"
fi

# ── Copy user-created agent skills (writable volume) ─────────
if [ -d "/user-agent-skills" ] && [ "$(ls -A /user-agent-skills 2>/dev/null)" ]; then
  mkdir -p "$HERMES_HOME/skills/user"
  cp -r /user-agent-skills/. "$HERMES_HOME/skills/user/"
  echo "→ User agent skills: $(ls $HERMES_HOME/skills/user/ | wc -l) files"
fi

# ── Cron profile (openrouter/free) — interactive chat keeps root config ──
echo "→ Ensuring Hermes cron profile (openrouter/free)..."
if [ -f /opt/lno-hermes/scripts/ensure_cron_profile.sh ]; then
  bash /opt/lno-hermes/scripts/ensure_cron_profile.sh || echo "  ⚠ cron profile setup skipped"
fi

# ── Register built-in cron jobs (idempotent) ─────────────────
echo "→ Setting up cron jobs..."

setup_cron() {
  local name="$1"
  local schedule="$2"
  local prompt="$3"

  if hermes cron list 2>/dev/null | grep -qF "$name"; then
    echo "  ✓ '$name' already registered"
  else
    hermes cron create "$schedule" "$prompt" --name "$name" --profile cron 2>&1 && \
      echo "  + '$name' registered ($schedule, profile=cron)" || \
      echo "  ✗ Failed to register '$name' — continuing"
  fi
}

setup_cron "lno-ops-monitor" "every 2 hours" \
  "Use the lno-ops-monitor skill. Scan all LNO OS workspaces for operational issues. Start with lno_list_workspaces to get workspace IDs, then run the full ops monitor protocol from the skill file."

setup_cron "lno-daily-digest" "0 8 * * *" \
  "Use the lno-daily-digest skill. Generate the morning digest for all LNO OS workspaces. Read current state, compare to yesterday's memory baseline, write digest, propose sending to #digest channel."

setup_cron "lno-product-manager" "0 9 * * 1" \
  "Use the lno-product-manager skill. Run the weekly product manager check for all LNO OS workspaces. Start with lno_list_workspaces to get workspace IDs, then follow the full PM protocol from the skill file."

setup_cron "lno-team-pulse" "0 16 * * 5" \
  "Use the lno-team-pulse skill. Run the weekly team pulse check for all LNO OS workspaces. Start with lno_list_workspaces to get workspace IDs, then follow the full team pulse protocol from the skill file."

setup_cron "lno-standup" "30 8 * * *" \
  "Morning standup coordinator. workspace_id is in DEFAULT_WORKSPACE_ID env — use it directly, do NOT call lno_list_workspaces. Call lno_get_workspace_memory. Read all team.report.* and team.standup.* keys. Write a 5-bullet morning summary for each team. Propose lno_send_channel_message to #standup channel. Do NOT create new cron jobs."

setup_cron "lno-memory-gardener" "0 3 * * 0" \
  "Use the lno-memory-gardener skill. Run weekly memory maintenance for all LNO OS workspaces. Start with lno_list_workspaces to get workspace IDs, then for each workspace follow the gardener protocol: read all memory (limit=100), dedupe/merge into canonical cross-linked pages, prune stale/duplicate keys with lno_delete_workspace_memory, keep the hot tier thin, and write memory.gardener.last_run. Be conservative — never delete a fact not preserved elsewhere. Do NOT create new cron jobs."

# ── Register user-created agent crons from skill files ────────
# Each .md file in /user-agent-skills with a SCHEDULE: header gets a cron
if [ -d "/user-agent-skills" ]; then
  for skill_file in /user-agent-skills/*.md; do
    [ -f "$skill_file" ] || continue
    agent_name=$(basename "$skill_file" .md)
    schedule=$(grep -m1 "^SCHEDULE:" "$skill_file" 2>/dev/null | sed 's/^SCHEDULE: *//' | tr -d '"')
    [ -z "$schedule" ] && continue
    setup_cron "user-$agent_name" "$schedule" \
      "Use the user/$agent_name skill. You are a custom LNO OS agent. Follow your skill file exactly."
  done
fi

# Point existing LNO crons at the free-model profile (safe to re-run)
if [ -f /opt/lno-hermes/scripts/ensure_cron_profile.sh ]; then
  bash /opt/lno-hermes/scripts/ensure_cron_profile.sh 2>/dev/null || true
fi

echo ""
echo "→ Starting Hermes dashboard on port 9119..."
# Dashboard exposes HTTP API for direct chat from LNO OS web app
hermes dashboard --host 0.0.0.0 --port 9119 --no-open --insecure --tui --skip-build &
DASHBOARD_PID=$!
echo "  Dashboard PID: $DASHBOARD_PID"

echo "→ Starting Hermes gateway (foreground mode)..."
echo "  Model: owl-alpha (OR acct 1) → OR acct 2 → Groq (fallback_providers)"
echo "  MCP:   http://api:8000/mcp/mcp"
echo "  Home:  $HERMES_HOME"
echo ""

# gateway run = foreground process — keep container alive
exec hermes gateway run
