#!/bin/bash
# ── LNO OS — One-command production deploy ─────────────────────
# Run on your server: bash deploy.sh
# Prerequisites: Docker, Docker Compose v2, .env.prod file present

set -euo pipefail

COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"
BACKUP_DIR="/opt/lno-backups"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  LNO OS deploy — $(date '+%Y-%m-%d %H:%M')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Preflight ──────────────────────────────────────────────────
if [ ! -f ".env.prod" ]; then
  echo "❌  .env.prod not found. Copy .env.prod.example and fill values."
  exit 1
fi

# ── Pull latest code ───────────────────────────────────────────
echo "→ Pulling latest code..."
git pull --ff-only

# ── Backup Postgres before any migration ──────────────────────
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/lno_os_$(date +%Y%m%d_%H%M%S).sql.gz"
echo "→ Backing up Postgres to $BACKUP_FILE..."
source .env.prod
$COMPOSE exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"
echo "   Backup complete ($(du -sh "$BACKUP_FILE" | cut -f1))"

# Keep last 7 backups
ls -t "$BACKUP_DIR"/*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm --

# ── Build images ───────────────────────────────────────────────
echo "→ Building images..."
$COMPOSE build --no-cache api web

# ── Run DB migrations ──────────────────────────────────────────
echo "→ Running database migrations..."
$COMPOSE run --rm api alembic upgrade head

# ── Restart services (zero-ish downtime: api → web → nginx) ───
echo "→ Restarting services..."
$COMPOSE up -d --remove-orphans

# ── Health check ──────────────────────────────────────────────
echo "→ Waiting for API health check..."
for i in $(seq 1 12); do
  if $COMPOSE exec -T api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✓ API healthy"
    break
  fi
  echo "   waiting... ($i/12)"
  sleep 5
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Deploy complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
$COMPOSE ps
