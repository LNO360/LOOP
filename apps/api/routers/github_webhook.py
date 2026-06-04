# apps/api/routers/github_webhook.py
"""
Public GitHub App webhook receiver.

POST /api/v1/webhooks/github
  — verifies HMAC-SHA256 signature
  — deduplicates by X-GitHub-Delivery
  — persists event to github_webhook_events
  — returns 200 immediately
  — fires BackgroundTask to process event
"""
import hashlib
import hmac
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.session import get_db
from models.github_webhook import GithubWebhookEvent, GithubAppInstallation

router = APIRouter(tags=["github-webhook"])

# Module-level constant — monkeypatched in tests
WEBHOOK_SECRET: str = ""

# Module-level reference to the handler — monkeypatched in tests.
# Imported lazily so tests can patch before the import resolves.
try:
    from core.github_webhook_handler import process_webhook_event
except ImportError:
    # Handler module will be created in Task 5; tests monkeypatch this name.
    def process_webhook_event(event_id):  # type: ignore[misc]
        pass


def _get_secret() -> str:
    return WEBHOOK_SECRET or settings.github_webhook_secret


async def _resolve_workspace(db: AsyncSession, installation_id: str) -> uuid.UUID | None:
    row = await db.execute(
        select(GithubAppInstallation).where(
            GithubAppInstallation.installation_id == installation_id
        )
    )
    inst = row.scalar_one_or_none()
    return inst.workspace_id if inst else None


@router.post("/webhooks/github")
@router.post("/github/webhook")   # alias: matches ngrok URL /api/github/webhook
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Receive a GitHub App webhook event."""
    body = await request.body()
    secret = _get_secret()

    # 1. Verify HMAC-SHA256 signature
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if not secret or not sig_header:
        raise HTTPException(status_code=401, detail="Invalid signature")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig_header, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. Parse event metadata
    event_type  = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", str(uuid.uuid4()))
    try:
        payload: dict = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # 3. Deduplicate — return 200 if we've seen this delivery before
    existing = await db.execute(
        select(GithubWebhookEvent).where(
            GithubWebhookEvent.delivery_id == delivery_id
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": True}

    # 4. Resolve workspace from installation
    installation_id = str(payload.get("installation", {}).get("id", ""))
    workspace_id = await _resolve_workspace(db, installation_id)

    # 5. Persist event
    event = GithubWebhookEvent(
        workspace_id=workspace_id,
        installation_id=installation_id,
        delivery_id=delivery_id,
        event_type=event_type,
        action=payload.get("action"),
        repo_full_name=(payload.get("repository") or {}).get("full_name"),
        payload=payload,
        status="received",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # 6. Dispatch background task — return 200 BEFORE it runs
    background_tasks.add_task(process_webhook_event, event.id)
    return {"ok": True}
