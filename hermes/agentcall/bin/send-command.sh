#!/usr/bin/env bash
# Send a JSON command to the active meeting bridge (Linux /proc stdin).
# Usage: send-command.sh '{"command":"tts.speak","text":"Hello"}'
set -euo pipefail

JSON="${1:?JSON command required}"
HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
PID_FILE="$HERMES_HOME/meetings/current/bridge.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "ERROR: No active bridge. Run start-bridge.sh first." >&2
  exit 1
fi

PID="$(cat "$PID_FILE")"
if ! kill -0 "$PID" 2>/dev/null; then
  echo "ERROR: Bridge process $PID is not running." >&2
  exit 1
fi

echo "$JSON" > "/proc/$PID/fd/0"
