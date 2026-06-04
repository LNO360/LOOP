"""Execute approved Google Workspace proposed actions (Gmail, Calendar, Sheets, Drive)."""
import base64
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.integrations import get_integration, get_google_access_token

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
CAL_BASE = "https://www.googleapis.com/calendar/v3"
SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_META = "https://www.googleapis.com/drive/v3/files"


async def _google_token(db: AsyncSession, workspace_id: str) -> str:
    row = await get_integration(db, workspace_id, "google")
    if not row:
        raise ValueError(
            "Google not connected. Connect at AI Work → Settings → Integrations."
        )
    return await get_google_access_token(row, db)


async def execute_gmail_send(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Send email via Gmail API after human approval."""
    token = await _google_token(db, workspace_id)
    to = payload["to"]
    subject = payload["subject"]
    body = payload["body"]
    reply_to_id: Optional[str] = payload.get("reply_to_id")

    extra_headers = ""
    thread_id = None
    if reply_to_id:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GMAIL_BASE}/messages/{reply_to_id}",
                headers={"Authorization": f"Bearer {token}"},
                params={"format": "metadata", "metadataHeaders": "Message-ID,Subject"},
                timeout=15,
            )
        if resp.status_code == 200:
            msg = resp.json()
            thread_id = msg.get("threadId")
            headers_map = {
                h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }
            msg_id = headers_map.get("message-id")
            if msg_id:
                extra_headers = f"In-Reply-To: {msg_id}\r\nReferences: {msg_id}\r\n"

    raw_message = (
        f"To: {to}\r\n"
        f"Subject: {subject}\r\n"
        f"{extra_headers}"
        f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        f"{body}"
    )
    encoded = base64.urlsafe_b64encode(raw_message.encode()).decode()
    send_body: dict = {"raw": encoded}
    if thread_id:
        send_body["threadId"] = thread_id

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_BASE}/messages/send",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=send_body,
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Gmail send failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return {"message_id": data.get("id"), "to": to, "subject": subject}


async def execute_gcal_create_event(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Create calendar event via Google Calendar API after human approval."""
    token = await _google_token(db, workspace_id)
    cal_id = payload.get("calendar_id") or "primary"
    event_body = {
        "summary": payload["title"],
        "start": {"dateTime": payload["start_iso"]},
        "end": {"dateTime": payload["end_iso"]},
    }
    if payload.get("description"):
        event_body["description"] = payload["description"]
    attendees = payload.get("attendees") or []
    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CAL_BASE}/calendars/{cal_id}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_body,
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Calendar create failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return {
        "event_id": data.get("id"),
        "title": data.get("summary"),
        "html_link": data.get("htmlLink"),
    }


async def execute_gcal_create_event_with_meet(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Create a calendar event with Google Meet link after human approval."""
    token = await _google_token(db, workspace_id)
    cal_id = payload.get("calendar_id") or "primary"
    event_body = {
        "summary": payload["title"],
        "start": {"dateTime": payload["start_iso"]},
        "end": {"dateTime": payload["end_iso"]},
        "conferenceData": {
            "createRequest": {
                "requestId": payload.get("request_id", "lno-meet-req"),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if payload.get("description"):
        event_body["description"] = payload["description"]
    attendees = payload.get("attendees") or []
    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CAL_BASE}/calendars/{cal_id}/events",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=event_body,
            params={"conferenceDataVersion": "1"},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Calendar create (Meet) failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    entry_points = data.get("conferenceData", {}).get("entryPoints", [])
    meet_link = next((ep.get("uri") for ep in entry_points if ep.get("entryPointType") == "video"), None)
    return {
        "event_id": data.get("id"),
        "title": data.get("summary"),
        "html_link": data.get("htmlLink"),
        "meet_link": meet_link,
    }


async def execute_gcal_update_event(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Update a calendar event via PATCH after human approval."""
    token = await _google_token(db, workspace_id)
    cal_id = payload.get("calendar_id") or "primary"
    event_id = payload["event_id"]
    patch = payload.get("patch", {})

    patch_body = {}
    if "title" in patch:
        patch_body["summary"] = patch["title"]
    if "start_iso" in patch:
        patch_body["start"] = {"dateTime": patch["start_iso"]}
    if "end_iso" in patch:
        patch_body["end"] = {"dateTime": patch["end_iso"]}
    if "description" in patch:
        patch_body["description"] = patch["description"]
    if "attendees" in patch:
        patch_body["attendees"] = [{"email": e} for e in patch["attendees"]]

    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{CAL_BASE}/calendars/{cal_id}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=patch_body,
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Calendar update failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return {"event_id": data.get("id"), "title": data.get("summary"), "html_link": data.get("htmlLink")}


async def execute_gcal_delete_event(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Delete a calendar event after human approval."""
    token = await _google_token(db, workspace_id)
    cal_id = payload.get("calendar_id") or "primary"
    event_id = payload["event_id"]

    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{CAL_BASE}/calendars/{cal_id}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    if resp.status_code == 404:
        raise ValueError(f"Event '{event_id}' not found — already deleted?")
    if resp.status_code >= 400:
        raise ValueError(f"Calendar delete failed ({resp.status_code}): {resp.text[:300]}")
    return {"deleted_event_id": event_id, "calendar_id": cal_id}


async def execute_gmail_add_label(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Add labels to a Gmail message after human approval."""
    token = await _google_token(db, workspace_id)
    message_id = payload["message_id"]
    label_ids = payload["label_ids"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_BASE}/messages/{message_id}/modify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"addLabelIds": label_ids},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Gmail add label failed ({resp.status_code}): {resp.text[:300]}")
    return {"message_id": message_id, "added_labels": label_ids}


async def execute_gmail_archive(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Archive a Gmail message (remove INBOX label) after human approval."""
    token = await _google_token(db, workspace_id)
    message_id = payload["message_id"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GMAIL_BASE}/messages/{message_id}/modify",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"removeLabelIds": ["INBOX"]},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Gmail archive failed ({resp.status_code}): {resp.text[:300]}")
    return {"message_id": message_id, "archived": True}


async def execute_gsheets_append_row(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Append a row to a Google Sheet after human approval."""
    token = await _google_token(db, workspace_id)
    spreadsheet_id = payload["spreadsheet_id"]
    sheet_name = payload["sheet_name"]
    values = payload["values"]
    import urllib.parse
    range_encoded = urllib.parse.quote(f"{sheet_name}!A1", safe="!:")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/{range_encoded}:append",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"values": [values], "majorDimension": "ROWS"},
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Sheets append failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return {
        "spreadsheet_id": spreadsheet_id,
        "updated_range": data.get("updates", {}).get("updatedRange"),
        "updated_rows": data.get("updates", {}).get("updatedRows", 1),
    }


async def execute_gsheets_update_cells(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Update a cell range in a Google Sheet after human approval."""
    token = await _google_token(db, workspace_id)
    spreadsheet_id = payload["spreadsheet_id"]
    range_a1 = payload["range_a1"]
    values = payload["values"]
    import urllib.parse
    range_encoded = urllib.parse.quote(range_a1, safe="!:")

    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/{range_encoded}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"range": range_a1, "values": values, "majorDimension": "ROWS"},
            params={"valueInputOption": "USER_ENTERED"},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Sheets update failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return {
        "spreadsheet_id": spreadsheet_id,
        "updated_range": data.get("updatedRange"),
        "updated_cells": data.get("updatedCells"),
    }


async def execute_gdrive_upload_file(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Upload a file to Google Drive after human approval."""
    import base64 as _b64
    import json as _json
    token = await _google_token(db, workspace_id)
    filename = payload["filename"]
    mime_type = payload["mime_type"]
    file_bytes = _b64.b64decode(payload["file_content_b64"])
    folder_id = payload.get("folder_id")

    metadata: dict = {"name": filename, "mimeType": mime_type}
    if folder_id:
        metadata["parents"] = [folder_id]

    # Multipart upload
    boundary = "lno_upload_boundary"
    meta_part = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        + _json.dumps(metadata)
        + f"\r\n--{boundary}\r\n"
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode()
    end_part = f"\r\n--{boundary}--".encode()
    body = meta_part + file_bytes + end_part

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            DRIVE_UPLOAD,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            content=body,
            params={"uploadType": "multipart", "fields": "id,name,webViewLink"},
            timeout=60,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Drive upload failed ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return {
        "file_id": data.get("id"),
        "name": data.get("name"),
        "web_view_link": data.get("webViewLink"),
    }
