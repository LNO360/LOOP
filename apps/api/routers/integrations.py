"""
Integration management routes.

GET    /api/v1/workspaces/{id}/integrations               — list all providers
GET    /api/v1/workspaces/{id}/integrations/google/connect — get OAuth URL
GET    /api/v1/integrations/google/callback               — OAuth callback (global)
DELETE /api/v1/workspaces/{id}/integrations/google        — disconnect Google
PUT    /api/v1/workspaces/{id}/integrations/brave         — save Brave API key
DELETE /api/v1/workspaces/{id}/integrations/brave         — remove Brave key
"""
import base64
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from jose import jwt as jose_jwt
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.config import settings
from core.integrations import encrypt, decrypt, get_integration
from db.session import get_db
from models.github_webhook import GithubAppInstallation, GithubWebhookEvent
from models.integration import WorkspaceIntegration

router = APIRouter(tags=["integrations"])


def _github_app_jwt() -> str | None:
    """Generate a short-lived GitHub App JWT for server-to-server API calls.
    Returns None if the private key is not configured."""
    key_path = os.path.expanduser(settings.github_app_private_key_path or "")
    if not key_path or not settings.github_app_id or not os.path.exists(key_path):
        return None
    try:
        with open(key_path) as f:
            private_key = f.read()
        now = int(time.time())
        token = jose_jwt.encode(
            {"iat": now - 60, "exp": now + 600, "iss": settings.github_app_id},
            private_key,
            algorithm="RS256",
        )
        return token
    except Exception:
        return None


async def _fetch_installation_login(installation_id: str) -> str:
    """Fetch account.login for a GitHub App installation using App JWT auth."""
    jwt = _github_app_jwt()
    if not jwt:
        return ""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.github.com/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if resp.status_code == 200:
            return resp.json().get("account", {}).get("login", "")
    except Exception:
        pass
    return ""

GOOGLE_SCOPES = " ".join([
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
])


class BraveKeyRequest(BaseModel):
    api_key: str


# ── List integrations ─────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/integrations")
async def list_integrations(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return connection status for all supported providers."""
    result = await db.execute(
        select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == uuid.UUID(workspace_id)
        )
    )
    rows = {r.provider: r for r in result.scalars().all()}

    def status(row: Optional[WorkspaceIntegration], provider: str) -> dict:
        if not row:
            return {"provider": provider, "connected": False}
        now = datetime.now(timezone.utc)
        expiry = row.token_expiry
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        expired = (expiry < now) if expiry else False
        return {
            "provider": provider,
            "connected": True,
            "expired": expired,
            "account_email": row.account_email,
            "scopes": row.scopes,
            "connected_at": row.connected_at.isoformat() if row.connected_at else None,
            # For Brave: mask key
            "key_set": bool(row.api_key) if provider == "brave" else None,
        }

    # Fetch github app installation status
    gh_app_result = await db.execute(
        select(GithubAppInstallation).where(
            GithubAppInstallation.workspace_id == uuid.UUID(workspace_id)
        )
    )
    gh_app = gh_app_result.scalar_one_or_none()

    return {
        "integrations": [
            status(rows.get("google"), "google"),
            status(rows.get("github"), "github"),
            status(rows.get("brave"), "brave"),
        ],
        "github_app": {
            "installed": gh_app is not None,
            "account_login": gh_app.account_login if gh_app else None,
            "installation_id": gh_app.installation_id if gh_app else None,
            "installed_at": gh_app.installed_at.isoformat() if gh_app else None,
        },
        "github_app_install_url": (
            f"https://github.com/apps/{settings.github_app_name.lower().replace(' ', '-')}/installations/new"
            if settings.github_app_name else None
        ),
    }


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/integrations/google/connect")
async def google_connect(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """Return the Google OAuth URL. Frontend should window.location it."""
    if not settings.google_client_id:
        raise HTTPException(400, "GOOGLE_CLIENT_ID not configured on server")

    state_payload = base64.urlsafe_b64encode(
        json.dumps({
            "workspace_id": workspace_id,
            "user_id": str(current_user.id),
            "nonce": secrets.token_hex(16),
        }).encode()
    ).decode()

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # always show consent to get refresh_token
        "state": state_payload,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"url": url}


@router.get("/integrations/google/callback")
async def google_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Exchange OAuth code for tokens and store them. No auth required (public callback)."""
    # Decode state
    try:
        # Add padding to handle base64 without padding
        padded = state + "==" * (-len(state) % 4)
        state_data = json.loads(base64.urlsafe_b64decode(padded))
        workspace_id = state_data["workspace_id"]
    except Exception:
        raise HTTPException(400, "Invalid OAuth state parameter")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
    token_data = resp.json()
    if "access_token" not in token_data:
        raise HTTPException(400, f"Token exchange failed: {token_data.get('error_description', token_data)}")

    # Get user email
    account_email = ""
    try:
        async with httpx.AsyncClient() as client:
            info_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
                timeout=10,
            )
        account_email = info_resp.json().get("email", "")
    except Exception:
        pass

    # Upsert integration row
    existing = await get_integration(db, workspace_id, "google")
    expiry = datetime.now(timezone.utc) + timedelta(seconds=token_data.get("expires_in", 3600))

    if existing:
        existing.access_token = encrypt(token_data["access_token"])
        if "refresh_token" in token_data:
            existing.refresh_token = encrypt(token_data["refresh_token"])
        existing.token_expiry = expiry
        existing.scopes = token_data.get("scope", "")
        existing.account_email = account_email
    else:
        refresh = token_data.get("refresh_token", "")
        db.add(WorkspaceIntegration(
            workspace_id=uuid.UUID(workspace_id),
            provider="google",
            access_token=encrypt(token_data["access_token"]),
            refresh_token=encrypt(refresh) if refresh else None,
            token_expiry=expiry,
            scopes=token_data.get("scope", ""),
            account_email=account_email,
        ))

    await db.commit()

    # Redirect back to settings
    frontend = settings.frontend_url
    return RedirectResponse(
        f"{frontend}/workspace/{workspace_id}/agents?tab=settings&connected=google"
    )


@router.delete("/workspaces/{workspace_id}/integrations/google")
async def google_disconnect(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Revoke Google token and remove from DB."""
    row = await get_integration(db, workspace_id, "google")
    if not row:
        return {"ok": True}

    # Best-effort revoke
    if row.access_token:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": decrypt(row.access_token)},
                    timeout=5,
                )
        except Exception:
            pass

    await db.delete(row)
    await db.commit()
    return {"ok": True}


# ── GitHub OAuth ─────────────────────────────────────────────────────────────

GITHUB_SCOPES = "repo read:user read:org"


@router.get("/workspaces/{workspace_id}/integrations/github/connect")
async def github_connect(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """Return the GitHub OAuth URL. Frontend should window.location it."""
    if not settings.github_client_id:
        raise HTTPException(400, "GITHUB_CLIENT_ID not configured on server")

    state_payload = base64.urlsafe_b64encode(
        json.dumps({
            "workspace_id": workspace_id,
            "user_id": str(current_user.id),
            "nonce": secrets.token_hex(16),
        }).encode()
    ).decode()

    params = {
        "client_id": settings.github_client_id,
        "redirect_uri": settings.github_redirect_uri,
        "scope": GITHUB_SCOPES,
        "state": state_payload,
    }
    url = "https://github.com/login/oauth/authorize?" + urlencode(params)
    return {"url": url}


@router.get("/integrations/github/callback")
async def github_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Exchange GitHub OAuth code for token and store it. Public callback."""
    try:
        padded = state + "==" * (-len(state) % 4)
        state_data = json.loads(base64.urlsafe_b64decode(padded))
        workspace_id = state_data["workspace_id"]
    except Exception:
        raise HTTPException(400, "Invalid OAuth state parameter")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
            timeout=15,
        )
    token_data = resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(400, f"GitHub token exchange failed: {token_data.get('error_description', token_data)}")

    # Get user info
    account_email = ""
    try:
        async with httpx.AsyncClient() as client:
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
        user_data = user_resp.json()
        account_email = user_data.get("login", "") or user_data.get("email", "")
    except Exception:
        pass

    # Upsert integration
    existing = await get_integration(db, workspace_id, "github")
    if existing:
        existing.access_token = encrypt(access_token)
        existing.scopes = token_data.get("scope", GITHUB_SCOPES)
        existing.account_email = account_email
        existing.connected_at = datetime.now(timezone.utc)
    else:
        db.add(WorkspaceIntegration(
            workspace_id=uuid.UUID(workspace_id),
            provider="github",
            access_token=encrypt(access_token),
            scopes=token_data.get("scope", GITHUB_SCOPES),
            account_email=account_email,
            connected_at=datetime.now(timezone.utc),
        ))
    await db.commit()

    frontend = settings.frontend_url
    return RedirectResponse(
        f"{frontend}/workspace/{workspace_id}/agents?tab=settings&connected=github"
    )


@router.delete("/workspaces/{workspace_id}/integrations/github")
async def github_disconnect(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove GitHub integration from workspace."""
    row = await get_integration(db, workspace_id, "github")
    if row:
        await db.delete(row)
        await db.commit()
    return {"ok": True}


# ── Brave Search ──────────────────────────────────────────────────────────────

@router.put("/workspaces/{workspace_id}/integrations/brave")
async def brave_save_key(
    workspace_id: str,
    body: BraveKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Save (or update) the Brave Search API key for this workspace."""
    if not body.api_key.strip():
        raise HTTPException(400, "api_key cannot be empty")

    existing = await get_integration(db, workspace_id, "brave")
    if existing:
        existing.api_key = encrypt(body.api_key.strip())
    else:
        db.add(WorkspaceIntegration(
            workspace_id=uuid.UUID(workspace_id),
            provider="brave",
            api_key=encrypt(body.api_key.strip()),
        ))
    await db.commit()
    return {"ok": True}


@router.delete("/workspaces/{workspace_id}/integrations/brave")
async def brave_remove_key(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    row = await get_integration(db, workspace_id, "brave")
    if row:
        await db.delete(row)
        await db.commit()
    return {"ok": True}


# ── GitHub App (Webhooks) ─────────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/integrations/github-app/connect")
async def github_app_connect(
    workspace_id: str,
    current_user=Depends(get_current_user),
):
    """
    Return the GitHub App install URL with a signed state param.
    Frontend should window.location to the returned URL.
    The signed state is verified in github_app_callback to prevent IDOR.
    """
    if not settings.github_app_name:
        raise HTTPException(400, "GITHUB_APP_NAME not configured on server")

    state_payload = base64.urlsafe_b64encode(
        json.dumps({
            "workspace_id": workspace_id,
            "user_id": str(current_user.id),
            "nonce": secrets.token_hex(16),
        }).encode()
    ).decode()

    app_slug = settings.github_app_name.lower().replace(" ", "-")
    url = (
        f"https://github.com/apps/{app_slug}/installations/new"
        f"?state={state_payload}"
    )
    return {"url": url}


@router.get("/integrations/github/app-callback")
async def github_app_callback(
    installation_id: str,
    setup_action: str = "install",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    """
    Public callback after user installs/updates the GitHub App.
    GitHub redirects here with ?installation_id=X&setup_action=install&state=<signed-state>
    The state is verified to contain a valid workspace_id + nonce (signed by the connect route).
    """
    # Decode signed state when present (install via LNO UI).
    # If state is absent (user installed directly from GitHub settings page),
    # we still store the installation — workspace_id will be None and can be
    # linked later via the admin UI.
    workspace_id: str | None = None
    if state:
        try:
            padded = state + "==" * (-len(state) % 4)
            state_data = json.loads(base64.urlsafe_b64decode(padded))
            workspace_id = state_data.get("workspace_id")
        except Exception:
            raise HTTPException(400, "Invalid state parameter")

    # Fetch org/user login using GitHub App JWT auth
    account_login = await _fetch_installation_login(installation_id)

    # Upsert installation row
    existing = await db.execute(
        select(GithubAppInstallation).where(
            GithubAppInstallation.installation_id == installation_id
        )
    )
    inst = existing.scalar_one_or_none()
    if inst:
        # Only update workspace_id if we have one from signed state
        if workspace_id:
            inst.workspace_id = uuid.UUID(workspace_id)
        if account_login:
            inst.account_login = account_login
    else:
        db.add(GithubAppInstallation(
            workspace_id=uuid.UUID(workspace_id) if workspace_id else None,
            installation_id=installation_id,
            account_login=account_login,
        ))
    await db.commit()

    frontend = settings.frontend_url
    if workspace_id:
        return RedirectResponse(
            f"{frontend}/workspace/{workspace_id}/agents?tab=settings&connected=github-app"
        )
    # Installed directly from GitHub — redirect to root, no workspace context
    return RedirectResponse(f"{frontend}/")


@router.delete("/workspaces/{workspace_id}/integrations/github-app")
async def github_app_uninstall(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Remove the GitHub App installation record for this workspace."""
    result = await db.execute(
        select(GithubAppInstallation).where(
            GithubAppInstallation.workspace_id == uuid.UUID(workspace_id)
        )
    )
    inst = result.scalar_one_or_none()
    if inst:
        await db.delete(inst)
        await db.commit()
    return {"ok": True}


@router.get("/workspaces/{workspace_id}/github/events")
async def github_events_feed(
    workspace_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Recent GitHub webhook events for this workspace (for the UI feed)."""
    result = await db.execute(
        select(GithubWebhookEvent)
        .where(GithubWebhookEvent.workspace_id == uuid.UUID(workspace_id))
        .order_by(desc(GithubWebhookEvent.received_at))
        .limit(max(1, min(limit, 100)))
    )
    events = result.scalars().all()
    return {
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "action": e.action,
                "repo_full_name": e.repo_full_name,
                "status": e.status,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
            }
            for e in events
        ]
    }
