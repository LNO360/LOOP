"""
Helpers for workspace integrations:
  - Fernet encrypt/decrypt for OAuth tokens
  - Google token refresh
  - Get integration or return error dict
"""
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.integration import WorkspaceIntegration


# ── Encryption ───────────────────────────────────────────────────────────────

def _fernet():
    """Return a Fernet instance. Falls back to a dev key if not configured."""
    from cryptography.fernet import Fernet
    key = settings.integration_encryption_key
    if not key:
        # Dev fallback — deterministic, insecure; fine for local dev
        # Must be exactly 32 bytes url-safe base64 encoded (44 chars)
        key = base64.urlsafe_b64encode(b"lno-os-dev-key-!!do-not-use-prod")
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt(value: str) -> str:
    """Encrypt a string value for DB storage."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt a previously encrypted string."""
    return _fernet().decrypt(value.encode()).decode()


# ── DB helpers ───────────────────────────────────────────────────────────────

async def get_integration(
    db: AsyncSession,
    workspace_id: str,
    provider: str,
) -> Optional[WorkspaceIntegration]:
    """Return the integration row or None."""
    import uuid
    ws_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
    result = await db.execute(
        select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == ws_uuid,
            WorkspaceIntegration.provider == provider,
        )
    )
    return result.scalar_one_or_none()


async def require_integration(
    db: AsyncSession,
    workspace_id: str,
    provider: str,
) -> "WorkspaceIntegration | dict":
    """
    Return the integration row, or an error dict if not found.
    MCP tools check: if isinstance(result, dict): return result
    """
    row = await get_integration(db, workspace_id, provider)
    if not row:
        return {
            "error": f"{provider.title()} not connected. "
                     "Ask a workspace admin to connect it at AI Work → Settings → Integrations."
        }
    return row


# ── Google token refresh ──────────────────────────────────────────────────────

async def get_google_access_token(
    integration: WorkspaceIntegration,
    db: AsyncSession,
) -> str:
    """
    Return a valid Google access token, refreshing if within 5 minutes of expiry.
    Updates DB in-place if refreshed.
    """
    now = datetime.now(timezone.utc)
    expiry = integration.token_expiry

    # Ensure expiry is timezone-aware for comparison
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    needs_refresh = (not expiry) or (expiry <= now + timedelta(minutes=5))

    if needs_refresh and integration.refresh_token:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": decrypt(integration.refresh_token),
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
        data = resp.json()
        if "access_token" not in data:
            raise ValueError(f"Token refresh failed: {data.get('error_description', data)}")

        integration.access_token = encrypt(data["access_token"])
        integration.token_expiry = now + timedelta(seconds=data.get("expires_in", 3600))
        await db.commit()

    return decrypt(integration.access_token)
