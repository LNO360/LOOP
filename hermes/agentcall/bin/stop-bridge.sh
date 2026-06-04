#!/usr/bin/env bash
# Gracefully stop the active meeting bridge.
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
DIR="$HERMES_HOME/meetings/current"
PID_FILE="$DIR/bridge.pid"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" 2>/dev/null; then
    /opt/lno-agentcall/bin/send-command.sh '{"command":"leave"}' 2>/dev/null || true
    sleep 2
    kill "$PID" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi

echo "bridge stopped"
