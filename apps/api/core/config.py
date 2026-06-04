from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os
import uuid

_ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env"))
if os.path.exists(_ROOT_ENV):
    load_dotenv(_ROOT_ENV, override=False)

class Settings(BaseSettings):
    database_url: str
    redis_url: str
    better_auth_secret: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "lno-files"
    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-v4-flash"
    openrouter_agent_model: str = "deepseek/deepseek-v4-flash"
    openrouter_fallback_model: str = "openrouter/free"
    # Scheduled digests, background agents, and similar — free model only
    openrouter_cron_model: str = "openrouter/free"
    hermes_service_token: str = ""

    # Auto-approve agent proposed actions (no human in the loop). When true, a
    # background sweeper executes pending low/medium-risk actions automatically;
    # high-risk deletes always stay pending for human approval. Env: AUTO_APPROVE_ENABLED
    auto_approve_enabled: bool = True

    # Embeddings (semantic memory search) — reuses OpenRouter's OpenAI-compatible
    # /embeddings endpoint, so no new key/provider/service is needed. Best-effort:
    # if disabled or unavailable, memory search falls back to keyword-only.
    embedding_enabled: bool = True
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dim: int = 1536  # must match the Vector(...) column + migration

    # Google OAuth (create at console.cloud.google.com)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"

    # Brave Search (legacy; MCP web_search uses SearXNG + DuckDuckGo)
    brave_search_api_key: str = ""

    # Web research — SearXNG in Docker (hermes + api on same host/network)
    searxng_url: str = "http://127.0.0.1:8080"
    web_search_timeout: float = 20.0
    web_fetch_timeout: float = 15.0

    # Encryption key for OAuth tokens in DB (32 url-safe base64 bytes)
    # Generate: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    integration_encryption_key: str = ""

    # GitHub OAuth App (create at github.com/settings/developers)
    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/v1/integrations/github/callback"
    # When set, GitHub MCP tools only access this org, not personal repos
    github_default_org: str = ""

    # Frontend origin — used for OAuth/App callback redirects back to the browser
    frontend_url: str = "http://localhost:3000"

    # GitHub App (webhooks) — create at github.com/settings/apps/new
    github_webhook_secret: str = ""            # GITHUB_WEBHOOK_SECRET env var
    github_app_id: str = ""                    # GITHUB_APP_ID
    github_app_name: str = ""                  # GITHUB_APP_NAME (slug for install URL)
    github_app_private_key_path: str = ""      # path to PEM, e.g. ~/.lno-secrets/github-app.private-key.pem

    # Telegram — notify + approve via Hermes chat
    telegram_bot_token: str = ""
    telegram_allowed_users: str = ""
    telegram_bot_name: str = ""   # bot username (no @)

    # lno.co.in blog CMS (Supabase) — service role key bypasses RLS for agent writes
    lno_site_supabase_url: str = ""
    lno_site_supabase_service_key: str = ""

    # lno.co.in site deploy (TanStack/Vercel) — Hermes + auto-redeploy after blog publish
    lno_site_vercel_deploy_hook: str = ""  # Vercel → Project → Settings → Deploy Hooks
    lno_site_github_repo: str = ""
    lno_site_github_branch: str = "main"
    lno_site_github_pat: str = ""  # optional server PAT for slug sync without workspace OAuth
    lno_site_auto_deploy_on_publish: bool = True

    # Scheduled digest — comma-separated workspace UUIDs only (empty = skip scheduler).
    # LNO Technologies production default; override in .env / .env.prod.
    digest_workspace_ids: str = ""

    model_config = SettingsConfigDict(
        env_file=_ROOT_ENV,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_hermes_token(self) -> str:
        return self.hermes_service_token or "dev-token-change-in-production"

    def digest_workspace_uuid_list(self) -> list[uuid.UUID]:
        """Workspaces eligible for the daily digest scheduler (explicit allowlist)."""
        raw = (self.digest_workspace_ids or "").strip()
        if not raw:
            return []
        out: list[uuid.UUID] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(uuid.UUID(part))
            except ValueError:
                continue
        return out

settings = Settings()
