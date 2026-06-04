#!/usr/bin/env bash
# Probe LNO OS MCP auth + tool registration (run on VPS: /opt/lno-os).
# Usage: ./scripts/probe-mcp.sh [.env.prod]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-${ROOT}/.env.prod}"
COMPOSE="docker compose --env-file ${ENV_FILE} -f ${ROOT}/docker-compose.prod.yml"

if [ ! -f "$ENV_FILE" ]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 1
fi

TOKEN=$(grep '^HERMES_SERVICE_TOKEN=' "$ENV_FILE" | cut -d= -f2- | tr -d '\r')
if [ -z "$TOKEN" ]; then
  echo "HERMES_SERVICE_TOKEN missing in $ENV_FILE" >&2
  exit 1
fi

echo "token length: ${#TOKEN}"

echo "→ API health"
$COMPOSE exec -T api curl -sf http://localhost:8000/health
echo ""

echo "→ MCP auth (wrong token must be 401)"
CODE=$($COMPOSE exec -T api curl -s -o /dev/null -w '%{http_code}' \
  -H 'Authorization: Bearer wrong-token' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}' \
  http://localhost:8000/mcp/mcp)
echo "  bad token POST → HTTP ${CODE} (want 401)"
if [ "$CODE" != "401" ]; then
  echo "  WARN: expected 401 for bad token" >&2
fi

echo "→ MCP initialize + tools/list (good token)"
BODY='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}'
RESP=$($COMPOSE exec -T api curl -s -w '\n__HTTP__%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$BODY" \
  http://localhost:8000/mcp/mcp)
HTTP=$(echo "$RESP" | tail -1 | sed 's/__HTTP__//')
PAYLOAD=$(echo "$RESP" | sed '$d')
echo "  initialize POST → HTTP ${HTTP}"
if [ "$HTTP" = "401" ]; then
  echo "  FAIL: service token rejected" >&2
  exit 1
fi
if [ "$HTTP" != "200" ] && [ "$HTTP" != "406" ]; then
  echo "  body: ${PAYLOAD:0:200}" >&2
fi

LIST_BODY='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
LIST=$($COMPOSE exec -T api curl -s \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d "$LIST_BODY" \
  http://localhost:8000/mcp/mcp | head -c 2000)
if echo "$LIST" | grep -q 'lno_list_tasks'; then
  echo "  tools/list → lno_list_tasks present ✓"
else
  echo "  tools/list preview: ${LIST:0:300}" >&2
  echo "  WARN: lno_list_tasks not seen in response (SSE JSON may need parsing)" >&2
fi

echo "→ bare GET (informational only — 400/406 is normal, not 401)"
GET_CODE=$($COMPOSE exec -T api curl -s -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Accept: application/json, text/event-stream' \
  http://localhost:8000/mcp/mcp)
echo "  GET /mcp/mcp → HTTP ${GET_CODE} (400/406 OK if not 401)"

echo "done"
