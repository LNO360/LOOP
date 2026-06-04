"""
Gmail MCP tools (workspace-level Google OAuth).

gmail_list_inbox   — recent emails
gmail_search       — search by query
gmail_get_email    — full email body
gmail_send         — send email (goes via proposed_action)
gmail_create_draft — save draft
"""
import base64
import uuid
from typing import Optional

import httpx
from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
from core.integrations import require_integration, get_google_access_token

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


async def _gmail_get(path: str, token: str, params: dict = None) -> dict:
    """Authenticated GET to Gmail API."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GMAIL_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
    if resp.status_code == 401:
        return {"error": "Google token expired. Ask admin to reconnect at AI Work → Settings → Integrations."}
    resp.raise_for_status()
    return resp.json()


async def _gmail_post(path: str, token: str, body: dict) -> dict:
    """Authenticated POST to Gmail API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )
    resp.raise_for_status()
    return resp.json()


def _parse_message_summary(msg: dict) -> dict:
    """Extract headers + snippet from a Gmail message resource."""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return {
        "id": msg.get("id"),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
    }


def _extract_body(payload: dict) -> str:
    """Recursively extract plain text body from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace") if data else ""
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


@mcp.tool()
async def gmail_list_inbox(
    workspace_id: str,
    max_results: int = 10,
) -> list[dict]:
    """
    List recent emails from the connected Gmail inbox.
    Returns [{id, subject, from, to, date, snippet}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    await agent_broadcast(workspace_id, "gmail_list_inbox", "running")
    data = await _gmail_get("/messages", token, {"maxResults": max_results, "labelIds": "INBOX"})
    if "error" in data:
        return [data]

    messages = data.get("messages", [])
    results = []
    for m in messages[:max_results]:
        full = await _gmail_get(f"/messages/{m['id']}", token, {
            "format": "metadata",
            "metadataHeaders": "Subject,From,To,Date",
        })
        if "error" not in full:
            results.append(_parse_message_summary(full))

    await agent_broadcast(workspace_id, "gmail_list_inbox", "done", f"{len(results)} emails")
    return results


@mcp.tool()
async def gmail_search(
    workspace_id: str,
    query: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Search Gmail using Gmail search syntax.
    Examples: 'from:alice@example.com', 'subject:invoice after:2026/01/01', 'is:unread'.
    Returns [{id, subject, from, to, date, snippet}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    await agent_broadcast(workspace_id, "gmail_search", "running", query)
    data = await _gmail_get("/messages", token, {"q": query, "maxResults": max_results})
    if "error" in data:
        return [data]

    messages = data.get("messages", [])
    results = []
    for m in messages:
        full = await _gmail_get(f"/messages/{m['id']}", token, {
            "format": "metadata",
            "metadataHeaders": "Subject,From,To,Date",
        })
        if "error" not in full:
            results.append(_parse_message_summary(full))

    await agent_broadcast(workspace_id, "gmail_search", "done", f"{len(results)} results for: {query}")
    return results


@mcp.tool()
async def gmail_get_email(
    workspace_id: str,
    message_id: str,
) -> dict:
    """
    Get the full content of an email by its message ID.
    Returns {id, subject, from, to, date, body, attachments}.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration
        token = await get_google_access_token(integration, db)

    data = await _gmail_get(f"/messages/{message_id}", token, {"format": "full"})
    if "error" in data:
        return data

    summary = _parse_message_summary(data)
    body = _extract_body(data.get("payload", {}))

    attachments = [
        {"filename": p.get("filename"), "mimeType": p.get("mimeType")}
        for p in data.get("payload", {}).get("parts", [])
        if p.get("filename")
    ]

    return {**summary, "body": body[:2000], "attachments": attachments}


@mcp.tool()
async def gmail_send(
    workspace_id: str,
    to: str,
    subject: str,
    body: str,
    reply_to_id: Optional[str] = None,
) -> dict:
    """
    Send an email. This is a write operation — it creates a proposed_action for human approval.
    reply_to_id: optional message ID to thread the reply under.
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration

        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="gmail_send",
            payload={"to": to, "subject": subject, "body": body, "reply_to_id": reply_to_id},
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)

    await agent_broadcast(workspace_id, "gmail_send", "done", f"Proposed: send to {to}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": f"Email to '{to}' queued for human approval in AI Work → Actions.",
    }


@mcp.tool()
async def gmail_create_draft(
    workspace_id: str,
    to: str,
    subject: str,
    body: str,
) -> dict:
    """
    Save an email draft in Gmail without sending it.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration
        token = await get_google_access_token(integration, db)

    raw_message = (
        f"To: {to}\r\nSubject: {subject}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n{body}"
    )
    encoded = base64.urlsafe_b64encode(raw_message.encode()).decode()

    data = await _gmail_post("/drafts", token, {"message": {"raw": encoded}})
    await agent_broadcast(workspace_id, "gmail_create_draft", "done", f"Draft saved: {subject}")
    return {"draft_id": data.get("id"), "message": "Draft saved in Gmail."}
