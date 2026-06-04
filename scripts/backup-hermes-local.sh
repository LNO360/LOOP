#!/usr/bin/env bash
# Backup Hermes SOUL, hot memory, skills, knowledge, cron jobs, and config to the host.
#
# Usage:
#   bash scripts/backup-hermes-local.sh              # → backups/hermes-YYYYMMDD-HHMMSS/
#   bash scripts/backup-hermes-local.sh --sync       # also refresh apps/hermes-data/knowledge/ from container
#   bash scripts/backup-hermes-local.sh --with-db    # include Postgres dump (requires postgres container)
#
# Run before VPS migration. Safe to run repeatedly.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${HERMES_CONTAINER:-lnoos-hermes-1}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${REPO_ROOT}/backups/hermes-${STAMP}"
SYNC_KNOWLEDGE=false
WITH_DB=false

for arg in "$@"; do
  case "$arg" in
    --sync) SYNC_KNOWLEDGE=true ;;
    --with-db) WITH_DB=true ;;
    -h|--help)
      echo "Usage: $0 [--sync] [--with-db]"
      exit 0
      ;;
  esac
done

mkdir -p "$DEST"/{repo,volume,manifest}

echo "→ Hermes local backup → $DEST"

copy_repo() {
  local src="$1" dst="$2"
  [ -e "$src" ] || return 0
  mkdir -p "$(dirname "$dst")"
  if [ -d "$src" ]; then
    cp -R "$src" "$dst"
  else
    cp "$src" "$dst"
  fi
}

echo "  repo: SOUL, config, hot memory, skills..."
copy_repo "${REPO_ROOT}/hermes/SOUL.md" "${DEST}/repo/hermes/SOUL.md"
copy_repo "${REPO_ROOT}/hermes/config.yaml" "${DEST}/repo/hermes/config.yaml"
copy_repo "${REPO_ROOT}/apps/hermes-data/memories" "${DEST}/repo/apps/hermes-data/memories"
copy_repo "${REPO_ROOT}/apps/hermes-skills" "${DEST}/repo/apps/hermes-skills"
copy_repo "${REPO_ROOT}/apps/user-agent-skills" "${DEST}/repo/apps/user-agent-skills"

if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "  volume: knowledge, cron, runtime skills, .env..."
  docker cp "${CONTAINER}:/root/.hermes/knowledge/." "${DEST}/volume/knowledge/" 2>/dev/null || mkdir -p "${DEST}/volume/knowledge"
  docker cp "${CONTAINER}:/root/.hermes/cron/." "${DEST}/volume/cron/" 2>/dev/null || true
  docker cp "${CONTAINER}:/root/.hermes/skills/lno/." "${DEST}/volume/skills-lno/" 2>/dev/null || true
  docker cp "${CONTAINER}:/root/.hermes/skills/user/." "${DEST}/volume/skills-user/" 2>/dev/null || true
  docker cp "${CONTAINER}:/root/.hermes/.env" "${DEST}/volume/hermes.env" 2>/dev/null || true
  docker exec "$CONTAINER" hermes cron list > "${DEST}/manifest/cron-list.txt" 2>/dev/null || true
else
  echo "  ⚠ Container $CONTAINER not running — skipped volume copy"
fi

if $SYNC_KNOWLEDGE && docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "  sync: apps/hermes-data/knowledge/ ← container"
  mkdir -p "${REPO_ROOT}/apps/hermes-data/knowledge"
  docker cp "${CONTAINER}:/root/.hermes/knowledge/." "${REPO_ROOT}/apps/hermes-data/knowledge/"
fi

if $WITH_DB && docker ps --format '{{.Names}}' | grep -qx 'lnoos-postgres-1'; then
  echo "  db: postgres dump..."
  docker compose -f "${REPO_ROOT}/docker-compose.yml" exec -T postgres \
    pg_dump -U lno lno_os | gzip > "${DEST}/manifest/lno_os.sql.gz"
fi

# Manifest
{
  echo "# Hermes backup manifest"
  echo "created: $(date -Iseconds)"
  echo "container: $CONTAINER"
  echo ""
  echo "## repo (git-tracked or bind-mounted)"
  echo "- hermes/SOUL.md — personality & protocols"
  echo "- hermes/config.yaml — MCP tools, model, toolsets"
  echo "- apps/hermes-data/memories/MEMORY.md — hot memory"
  echo "- apps/hermes-data/memories/USER.md — user profile"
  echo "- apps/hermes-skills/ — built-in skills"
  echo "- apps/user-agent-skills/ — custom agent skills"
  echo ""
  echo "## volume (Docker hermes-data — copy before migrate)"
  echo "- volume/knowledge/ — research docs, runbooks"
  echo "- volume/cron/ — scheduled jobs (jobs.json)"
  echo "- volume/skills-lno/ — runtime copy of built-in skills"
  echo "- volume/skills-user/ — runtime copy of user skills"
  echo "- volume/hermes.env — API keys (KEEP PRIVATE)"
  echo ""
  echo "## warm memory"
  echo "Workspace facts (team.report.*, dashboard.*) live in Postgres workspace_memories."
  echo "Use --with-db or pg_dump separately before migration."
  echo ""
  echo "## restore on VPS"
  echo "1. git clone repo (gets SOUL, memories, skills)"
  echo "2. tar xzf hermes_data_backup.tar.gz into hermes-data volume"
  echo "3. Or: gdrive_search + gdrive_read_file for cloud copies"
  echo "4. pg_restore for DB + warm memory"
} > "${DEST}/manifest/README.md"

# Archive
ARCHIVE="${REPO_ROOT}/backups/hermes-${STAMP}.tar.gz"
tar -czf "$ARCHIVE" -C "${REPO_ROOT}/backups" "hermes-${STAMP}"
SIZE="$(du -sh "$ARCHIVE" | cut -f1)"

echo ""
echo "✓ Backup complete"
echo "  folder: $DEST"
echo "  archive: $ARCHIVE ($SIZE)"
echo ""
echo "Next: upload archive to Drive, or run with --sync to keep knowledge in apps/hermes-data/knowledge/"
