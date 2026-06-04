"""
Google Drive MCP tools.

Read:  gdrive_search, gdrive_list_folder, gdrive_read_file, gdrive_get_file_info
Write: gdrive_upload_file (proposed_action — human approval)
"""
import base64
import httpx
from typing import Optional
from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
from core.integrations import require_integration, get_google_access_token
from models.agent import ProposedAction
import uuid

DRIVE_BASE = "https://www.googleapis.com/drive/v3"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


async def _drive_get(path: str, token: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DRIVE_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
    if resp.status_code == 401:
        return {"error": "Google token expired. Reconnect at AI Work → Settings → Integrations."}
    resp.raise_for_status()
    return resp.json()


FILE_FIELDS = "id,name,mimeType,size,modifiedTime,owners,webViewLink,parents"


@mcp.tool()
async def gdrive_search(
    workspace_id: str,
    query: str,
    max_results: int = 10,
) -> list[dict]:
    """
    Search Google Drive files by name or content.
    Query examples: 'name contains "budget"', 'fullText contains "Q2 report"',
                    'mimeType = "application/vnd.google-apps.document"'
    Returns [{id, name, mimeType, modifiedTime, webViewLink}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    await agent_broadcast(workspace_id, "gdrive_search", "running", query)
    data = await _drive_get("/files", token, {
        "q": query,
        "pageSize": max_results,
        "fields": f"files({FILE_FIELDS})",
        "orderBy": "modifiedTime desc",
    })
    if "error" in data:
        return [data]

    files = data.get("files", [])
    await agent_broadcast(workspace_id, "gdrive_search", "done", f"{len(files)} files")
    return [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "mimeType": f.get("mimeType"),
            "modifiedTime": f.get("modifiedTime"),
            "webViewLink": f.get("webViewLink"),
        }
        for f in files
    ]


@mcp.tool()
async def gdrive_list_folder(
    workspace_id: str,
    folder_id: Optional[str] = None,
    max_results: int = 50,
) -> list[dict]:
    """
    List files in a Google Drive folder.
    folder_id: omit or pass 'root' to list root.
    Returns [{id, name, mimeType, modifiedTime, webViewLink, isFolder}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    parent = folder_id or "root"
    data = await _drive_get("/files", token, {
        "q": f"'{parent}' in parents and trashed = false",
        "pageSize": max_results,
        "fields": f"files({FILE_FIELDS})",
        "orderBy": "folder,name",
    })
    if "error" in data:
        return [data]

    return [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "mimeType": f.get("mimeType"),
            "modifiedTime": f.get("modifiedTime"),
            "webViewLink": f.get("webViewLink"),
            "isFolder": f.get("mimeType") == "application/vnd.google-apps.folder",
        }
        for f in data.get("files", [])
    ]


@mcp.tool()
async def gdrive_read_file(
    workspace_id: str,
    file_id: str,
    max_chars: int = 8000,
) -> dict:
    """
    Read the content of a Google Doc, Sheet (as CSV), or plain text file.
    For binary files, returns metadata only.
    Returns {id, name, content, truncated}.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration
        token = await get_google_access_token(integration, db)

    # Get metadata first
    meta = await _drive_get(f"/files/{file_id}", token, {"fields": "id,name,mimeType"})
    if "error" in meta:
        return meta

    mime = meta.get("mimeType", "")
    name = meta.get("name", "")

    # Export map for Google Workspace types
    export_mime = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    if mime in export_mime:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}/export",
                headers={"Authorization": f"Bearer {token}"},
                params={"mimeType": export_mime[mime]},
                timeout=20,
            )
        text = resp.text
    elif mime.startswith("text/"):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{DRIVE_BASE}/files/{file_id}?alt=media",
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
        text = resp.text
    else:
        return {"id": file_id, "name": name, "content": None,
                "message": f"Binary file ({mime}) — cannot read as text."}

    truncated = len(text) > max_chars
    await agent_broadcast(workspace_id, "gdrive_read_file", "done", name)
    return {
        "id": file_id,
        "name": name,
        "content": text[:max_chars],
        "truncated": truncated,
        "total_chars": len(text),
    }


@mcp.tool()
async def gdrive_get_file_info(
    workspace_id: str,
    file_id: str,
) -> dict:
    """
    Get metadata for a Drive file: owner, size, sharing, modified time.
    Returns {id, name, mimeType, size, modifiedTime, owners, webViewLink, parents}.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration
        token = await get_google_access_token(integration, db)

    data = await _drive_get(f"/files/{file_id}", token, {"fields": FILE_FIELDS})
    if "error" in data:
        return data

    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "mimeType": data.get("mimeType"),
        "size": data.get("size"),
        "modifiedTime": data.get("modifiedTime"),
        "owners": [o.get("emailAddress") for o in data.get("owners", [])],
        "webViewLink": data.get("webViewLink"),
        "parents": data.get("parents", []),
    }


@mcp.tool()
async def gdrive_upload_file(
    workspace_id: str,
    filename: str,
    content: str,
    folder_id: Optional[str] = None,
    mime_type: str = "text/markdown",
) -> dict:
    """
    Upload a text or markdown file to Google Drive. Creates a proposed_action for human approval.
    Max 10 MB. After approval, returns file_id and webViewLink in execution_result.

    filename: e.g. "indian-telecom-law-compliance-guide.md"
    content: full file text (read local file with terminal/cat first if needed)
    folder_id: optional Drive folder ID; omit to upload to root
    mime_type: default text/markdown; use text/plain for .txt files
    """
    raw = content.encode("utf-8")
    if len(raw) > MAX_UPLOAD_BYTES:
        return {
            "proposed": False,
            "error": f"File too large ({len(raw)} bytes). Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        }

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration

        payload = {
            "filename": filename,
            "mime_type": mime_type,
            "file_content_b64": base64.b64encode(raw).decode("ascii"),
            "folder_id": folder_id,
            "size_kb": round(len(raw) / 1024, 1),
        }
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="gdrive_upload_file",
            payload=payload,
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)

        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="gdrive_upload_file",
            payload=payload,
        )

    await agent_broadcast(workspace_id, "gdrive_upload_file", "done", f"Proposed: {filename}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": (
            f"Upload '{filename}' queued for approval. "
            "After approve, store returned file_id via lno_upsert_workspace_memory "
            "(key: research.drive.files.{slug})."
        ),
    }
