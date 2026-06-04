#!/usr/bin/env bash
# Fetch AgentCall transcript JSON after call.ended (reads call_id from events file).
# Usage: fetch-transcript.sh [events.jsonl]
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
EVENTS="${1:-$HERMES_HOME/meetings/current/events.jsonl}"

if [ ! -f "$EVENTS" ]; then
  echo "ERROR: events file not found: $EVENTS" >&2
  exit 1
fi

CALL_ID="$(grep -oE '"call_id"[[:space:]]*:[[:space:]]*"[^"]+"' "$EVENTS" | tail -1 | sed -E 's/.*"([^"]+)"$/\1/')"

if [ -z "$CALL_ID" ]; then
  echo "ERROR: call_id not found in $EVENTS" >&2
  exit 1
fi

API_KEY="${AGENTCALL_API_KEY:-}"
if [ -z "$API_KEY" ] && [ -f "$HOME/.agentcall/config.json" ]; then
  API_KEY="$(python3 -c "import json; print(json.load(open('$HOME/.agentcall/config.json')).get('api_key',''))")"
fi
if [ -z "$API_KEY" ]; then
  echo "ERROR: AGENTCALL_API_KEY not set" >&2
  exit 1
fi

curl -sf "https://api.agentcall.dev/v1/calls/${CALL_ID}/transcript?format=json" \
  -H "Authorization: Bearer ${API_KEY}"
