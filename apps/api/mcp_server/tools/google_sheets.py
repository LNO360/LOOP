"""
Google Sheets MCP tools (workspace-level Google OAuth).

gsheets_list_spreadsheets — list spreadsheets (name, id, modified)
gsheets_get_metadata      — sheet tabs, row/col counts
gsheets_read_range        — read A1 range → rows (capped)
gsheets_append_row        — append row (proposed_action, medium risk)
gsheets_update_cells      — update range (proposed_action, medium risk)
"""
import uuid
from typing import Optional

import httpx
from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
from core.integrations import require_integration, get_google_access_token

SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_BASE = "https://www.googleapis.com/drive/v3"

MAX_ROWS = 500
MAX_COLS = 50


async def _sheets_get(path: str, token: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SHEETS_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
    if resp.status_code == 401:
        return {"error": "Google token expired. Reconnect at AI Work → Settings → Integrations."}
    if resp.status_code >= 400:
        return {"error": f"Sheets API error {resp.status_code}: {resp.text[:300]}"}
    return resp.json()


async def _sheets_put(path: str, token: str, body: dict, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{SHEETS_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            params=params or {},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Sheets API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


async def _sheets_post(path: str, token: str, body: dict, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SHEETS_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            params=params or {},
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"Sheets API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


@mcp.tool()
async def gsheets_list_spreadsheets(
    workspace_id: str,
    max_results: int = 20,
) -> list[dict]:
    """
    List Google Sheets spreadsheets accessible to the connected account.
    Returns [{id, name, modifiedTime, webViewLink}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DRIVE_BASE}/files",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "q": "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
                "pageSize": min(max_results, 100),
                "fields": "files(id,name,modifiedTime,webViewLink)",
                "orderBy": "modifiedTime desc",
            },
            timeout=15,
        )
    if resp.status_code == 401:
        return [{"error": "Google token expired. Reconnect at AI Work → Settings → Integrations."}]
    if resp.status_code >= 400:
        return [{"error": f"Drive API error {resp.status_code}: {resp.text[:300]}"}]

    files = resp.json().get("files", [])
    await agent_broadcast(workspace_id, "gsheets_list_spreadsheets", "done", f"{len(files)} spreadsheets")
    return [
        {
            "id": f["id"],
            "name": f["name"],
            "modifiedTime": f.get("modifiedTime"),
            "webViewLink": f.get("webViewLink"),
        }
        for f in files
    ]


@mcp.tool()
async def gsheets_get_metadata(
    workspace_id: str,
    spreadsheet_id: str,
) -> dict:
    """
    Get spreadsheet metadata: title, sheet tabs with row/col counts.
    Returns {spreadsheet_id, title, sheets: [{sheet_id, title, row_count, col_count}]}.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration
        token = await get_google_access_token(integration, db)

    data = await _sheets_get(
        f"/{spreadsheet_id}",
        token,
        {"fields": "spreadsheetId,properties,sheets.properties"},
    )
    if "error" in data:
        return data

    sheets = [
        {
            "sheet_id": s["properties"].get("sheetId"),
            "title": s["properties"].get("title"),
            "row_count": s["properties"].get("gridProperties", {}).get("rowCount"),
            "col_count": s["properties"].get("gridProperties", {}).get("columnCount"),
        }
        for s in data.get("sheets", [])
    ]
    return {
        "spreadsheet_id": data.get("spreadsheetId"),
        "title": data.get("properties", {}).get("title"),
        "sheets": sheets,
    }


@mcp.tool()
async def gsheets_read_range(
    workspace_id: str,
    spreadsheet_id: str,
    range_a1: str,
) -> dict:
    """
    Read a range from a Google Sheet using A1 notation.
    range_a1 examples: 'Sheet1!A1:D20', 'A:Z', 'Sheet2!B2:E10'.
    Rows capped at 500, columns at 50.
    Returns {spreadsheet_id, range, values: [[...]], truncated, total_rows}.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration
        token = await get_google_access_token(integration, db)

    import urllib.parse
    encoded_range = urllib.parse.quote(range_a1, safe="!:")
    data = await _sheets_get(f"/{spreadsheet_id}/values/{encoded_range}", token)
    if "error" in data:
        return data

    values = data.get("values", [])
    capped = [row[:MAX_COLS] for row in values[:MAX_ROWS]]
    truncated = len(values) > MAX_ROWS or any(len(r) > MAX_COLS for r in values)

    await agent_broadcast(workspace_id, "gsheets_read_range", "done", f"{len(capped)} rows from {range_a1}")
    return {
        "spreadsheet_id": spreadsheet_id,
        "range": data.get("range", range_a1),
        "values": capped,
        "truncated": truncated,
        "total_rows": len(values),
    }


@mcp.tool()
async def gsheets_append_row(
    workspace_id: str,
    spreadsheet_id: str,
    sheet_name: str,
    values: list,
) -> dict:
    """
    Append a row to a Google Sheet. Write operation — creates proposed_action for human approval.
    values: flat list of cell values for the new row e.g. ["Alice", 42, "2026-01-01"].
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration

        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="gsheets_append_row",
            payload={
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "values": values,
            },
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="gsheets_append_row",
            payload={
                "spreadsheet_id": spreadsheet_id,
                "sheet_name": sheet_name,
                "values": str(values)[:120],
            },
        )

    await agent_broadcast(workspace_id, "gsheets_append_row", "done", f"Proposed: append to {sheet_name}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": f"Append row to '{sheet_name}' queued for approval in AI Work → Actions.",
    }


@mcp.tool()
async def gsheets_update_cells(
    workspace_id: str,
    spreadsheet_id: str,
    range_a1: str,
    values: list[list],
) -> dict:
    """
    Update a range of cells in a Google Sheet. Write operation — creates proposed_action.
    range_a1: A1 notation e.g. 'Sheet1!B2:D4'.
    values: 2D array matching the range e.g. [["a","b"],["c","d"]].
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration

        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="gsheets_update_cells",
            payload={
                "spreadsheet_id": spreadsheet_id,
                "range_a1": range_a1,
                "values": values,
            },
            risk_level="medium",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="gsheets_update_cells",
            payload={
                "spreadsheet_id": spreadsheet_id,
                "range_a1": range_a1,
                "rows": len(values),
            },
        )

    await agent_broadcast(workspace_id, "gsheets_update_cells", "done", f"Proposed: update {range_a1}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": f"Update cells '{range_a1}' queued for approval in AI Work → Actions.",
    }
