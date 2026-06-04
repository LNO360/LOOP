# Deployment

## Prerequisites

- Docker and Docker Compose v2
- A server (VPS or bare metal) with 2 GB+ RAM
- A domain name with DNS pointed at your server
- (Optional) Telegram bot token for the Hermes agent

## Local development

```bash
cp .env.example .env
# Edit .env — minimum: DATABASE_URL, BETTER_AUTH_SECRET, S3_* keys
docker compose up -d
```

Services:
- Web UI: http://localhost:3000
- API: http://localhost:8000
- MinIO console: http://localhost:9001

## Production deployment

### 1. Prepare the server

```bash
git clone https://github.com/your-org/lno-os.git /opt/lno-os
cd /opt/lno-os

cp .env.prod.example .env.prod
nano .env.prod   # fill every value — see inline comments
```

### 2. Configure your domain

Edit `Caddyfile` — replace `your-domain.com` with your actual domain and set a real email for Let's Encrypt certificate notices.

### 3. Deploy

```bash
bash deploy.sh
```

The `deploy.sh` script:
1. Pulls the latest code (`git pull`)
2. Backs up PostgreSQL to `/opt/lno-backups/` (keeps last 7)
3. Builds Docker images (`api`, `web`)
4. Runs Alembic migrations
5. Restarts all services
6. Runs an API health check

### 4. CI/CD with GitHub Actions (optional)

The included workflow (`.github/workflows/deploy.yml`) triggers a Coolify deploy webhook on push to `main`.

Add these secrets to your GitHub repo:
- `COOLIFY_WEBHOOK_URL`
- `COOLIFY_WEBHOOK_TOKEN`

## Environment variables

`.env.example` — development defaults with inline documentation
`.env.prod.example` — production template with inline documentation

Every variable has a comment explaining what it is and how to generate it.

## Database migrations

```bash
# Run migrations manually
docker compose exec api alembic upgrade head

# Create a new migration
docker compose exec api alembic revision --autogenerate -m "description"
```

## Backups

PostgreSQL backups are written automatically by `deploy.sh` to `/opt/lno-backups/`.

Hermes memory and knowledge files live in the `hermes-data` Docker volume. Back it up with:

```bash
docker run --rm -v lnoos_hermes-data:/data -v /opt/lno-backups:/out \
  alpine tar czf /out/hermes-data-$(date +%Y%m%d).tar.gz -C /data .
```
