#!/bin/bash
# Hermes cron hygiene — pause duplicate/superseded jobs and fix deliver:origin failures.
# Run: docker exec lnoos-hermes-1 bash /opt/lno-hermes/scripts/cleanup_crons.sh
#
# Safe to run repeatedly (idempotent pauses).

set -e

echo "→ Hermes cron cleanup"

pause_if_exists() {
  local name="$1"
  if hermes cron list 2>/dev/null | grep -qF "$name"; then
    hermes cron pause "$name" 2>/dev/null && echo "  ⏸ paused $name" || echo "  · $name (already paused or pause unsupported)"
  fi
}

unpause_if_exists() {
  local name="$1"
  if hermes cron list 2>/dev/null | grep -qF "$name"; then
    hermes cron unpause "$name" 2>/dev/null && echo "  ▶ unpaused $name" || echo "  · $name (unpause skipped)"
  fi
}

# ── Pause known duplicates / superseded versions ─────────────────────────────
DUPLICATES=(
  "lno-ops-monitor-v2"
)

for job in "${DUPLICATES[@]}"; do
  pause_if_exists "$job"
done

# ── Ensure canonical built-in jobs are active ────────────────────────────────
CANONICAL=(
  "lno-ops-monitor"
  "lno-daily-digest"
  "lno-standup"
  "lno-product-manager"
  "lno-team-pulse"
)

for job in "${CANONICAL[@]}"; do
  unpause_if_exists "$job"
done

echo ""
echo "→ Current cron jobs:"
hermes cron list 2>/dev/null || echo "  (hermes cron list unavailable)"

echo ""
echo "Done. Jobs with deliver=origin failures need manual fix:"
echo "  hermes cron edit <name> --deliver local"
echo "  or pause if superseded by a deliver:local copy."
