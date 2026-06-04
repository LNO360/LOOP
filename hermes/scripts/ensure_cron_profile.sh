#!/bin/bash
# Ensure Hermes "cron" profile uses openrouter/free; apply to LNO scheduled jobs.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
CRON_CFG_SRC="${CRON_CFG_SRC:-/opt/lno-hermes/profile-cron-config.yaml}"

ensure_cron_profile() {
  mkdir -p "$HERMES_HOME/profiles/cron"
  if [ -f "$CRON_CFG_SRC" ]; then
    cp "$CRON_CFG_SRC" "$HERMES_HOME/profiles/cron/config.yaml"
  fi
  if ! hermes profile list 2>/dev/null | grep -qE '(^| )cron( |$)'; then
    hermes profile create cron --no-alias --no-skills \
      --description "Scheduled LNO jobs — openrouter/free only" 2>/dev/null || true
    [ -f "$CRON_CFG_SRC" ] && cp "$CRON_CFG_SRC" "$HERMES_HOME/profiles/cron/config.yaml"
  fi
}

apply_cron_profile_to_jobs() {
  local id="" name=""
  while IFS= read -r line; do
    if [[ "$line" =~ ^[[:space:]]*([a-f0-9]{12})[[:space:]]+\[ ]]; then
      id="${BASH_REMATCH[1]}"
      name=""
    elif [[ "$line" =~ Name:[[:space:]]*(.+) ]]; then
      name="${BASH_REMATCH[1]// /}"
      if [[ "$name" == lno-* || "$name" == user-* || "$name" == github-guardian ]]; then
        if hermes cron edit "$id" --profile cron 2>/dev/null; then
          echo "  ✓ cron job '$name' → profile cron (openrouter/free)"
        fi
      fi
    fi
  done < <(hermes cron list 2>/dev/null || true)
}

ensure_cron_profile
apply_cron_profile_to_jobs
