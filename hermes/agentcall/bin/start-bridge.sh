#!/usr/bin/env bash
# Start AgentCall voice bridge for Hermes (Linux / Docker).
# Usage: start-bridge.sh <meet-url>
set -euo pipefail

URL="${1:?Meeting URL required (Google Meet, Zoom, or Teams)}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
DIR="$HERMES_HOME/meetings/current"
PYTHON="${PYTHON:-/opt/hermes/.venv/bin/python}"
BRIDGE="/opt/lno-agentcall/scripts/python/bridge.py"

mkdir -p "$DIR"
EVENTS="$DIR/events.jsonl"
: > "$EVENTS"

if [ -f "$DIR/bridge.pid" ]; then
  old_pid="$(cat "$DIR/bridge.pid")"
  if kill -0 "$old_pid" 2>/dev/null; then
    echo "Stopping previous bridge (pid $old_pid)"
    kill "$old_pid" 2>/dev/null || true
    sleep 1
  fi
fi

if [ ! -f "$BRIDGE" ]; then
  echo "ERROR: bridge not found at $BRIDGE" >&2
  exit 1
fi

if [ -z "${AGENTCALL_API_KEY:-}" ] && [ ! -f "$HOME/.agentcall/config.json" ]; then
  echo "ERROR: Set AGENTCALL_API_KEY or ~/.agentcall/config.json" >&2
  exit 1
fi

"$PYTHON" "$BRIDGE" "$URL" \
  --name "Hermes" \
  --voice af_heart \
  --voice-strategy direct \
  --output "$EVENTS" \
  >"$DIR/bridge.stdout.log" 2>"$DIR/bridge.stderr.log" &
echo $! > "$DIR/bridge.pid"

echo "bridge_pid=$(cat "$DIR/bridge.pid")"
echo "events_file=$EVENTS"
echo "commands: /opt/lno-agentcall/bin/send-command.sh '<json>'"
