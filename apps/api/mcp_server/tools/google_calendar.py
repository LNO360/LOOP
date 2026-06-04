"""
Google Calendar MCP tools.

gcal_list_events     — events in a date range
gcal_find_free_slots — open time blocks
gcal_create_event    — create event (proposed_action)
gcal_list_calendars  — list all calendars
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
from core.integrations import require_integration, get_google_access_token

CAL_BASE = "https://www.googleapis.com/calendar/v3"


async def _cal_get(path: str, token: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CAL_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
            timeout=15,
        )
    if resp.status_code == 401:
        return {"error": "Google token expired. Reconnect at AI Work → Settings → Integrations."}
    resp.raise_for_status()
    return resp.json()


async def _cal_post(path: str, token: str, body: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CAL_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
            timeout=15,
        )
    resp.raise_for_status()
    return resp.json()


def _parse_event(e: dict) -> dict:
    start = e.get("start", {})
    end = e.get("end", {})
    return {
        "id": e.get("id"),
        "title": e.get("summary", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "location": e.get("location"),
        "description": (e.get("description") or "")[:500],
        "attendees": [a.get("email") for a in e.get("attendees", [])],
        "status": e.get("status"),
    }


@mcp.tool()
async def gcal_list_events(
    workspace_id: str,
    days_ahead: int = 7,
    calendar_id: Optional[str] = None,
) -> list[dict]:
    """
    List upcoming calendar events.
    days_ahead: how many days forward to look (default 7).
    calendar_id: specific calendar ID, or omit for primary.
    Returns [{id, title, start, end, location, attendees, status}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    cal = calendar_id or "primary"
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days_ahead)

    await agent_broadcast(workspace_id, "gcal_list_events", "running")
    data = await _cal_get(f"/calendars/{cal}/events", token, {
        "timeMin": now.isoformat(),
        "timeMax": time_max.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 50,
    })
    if "error" in data:
        return [data]

    events = [_parse_event(e) for e in data.get("items", [])]
    await agent_broadcast(workspace_id, "gcal_list_events", "done", f"{len(events)} events")
    return events


@mcp.tool()
async def gcal_find_free_slots(
    workspace_id: str,
    duration_minutes: int,
    days_ahead: int = 5,
    calendar_id: Optional[str] = None,
) -> list[dict]:
    """
    Find free time slots with no calendar conflicts.
    duration_minutes: required meeting length.
    Returns [{start, end, duration_minutes}] — up to 10 slots.
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    cal = calendar_id or "primary"
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    # Working hours: 09:00–18:00 UTC
    duration = timedelta(minutes=duration_minutes)
    slots = []

    for day_offset in range(days_ahead):
        day_start = now + timedelta(days=day_offset)
        day_start = day_start.replace(hour=9)
        day_end = day_start.replace(hour=18)

        events_data = await _cal_get(f"/calendars/{cal}/events", token, {
            "timeMin": day_start.isoformat(),
            "timeMax": day_end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
        })
        if "error" in events_data:
            return [events_data]

        busy = []
        for e in events_data.get("items", []):
            s = e.get("start", {}).get("dateTime")
            en = e.get("end", {}).get("dateTime")
            if s and en:
                busy.append((datetime.fromisoformat(s), datetime.fromisoformat(en)))

        # Find gaps
        cursor = day_start
        for (bs, be) in sorted(busy):
            if cursor + duration <= bs:
                slots.append({
                    "start": cursor.isoformat(),
                    "end": (cursor + duration).isoformat(),
                    "duration_minutes": duration_minutes,
                })
            cursor = max(cursor, be)
            if len(slots) >= 10:
                break
        if cursor + duration <= day_end and len(slots) < 10:
            slots.append({
                "start": cursor.isoformat(),
                "end": (cursor + duration).isoformat(),
                "duration_minutes": duration_minutes,
            })

        if len(slots) >= 10:
            break

    return slots[:10]


@mcp.tool()
async def gcal_create_event(
    workspace_id: str,
    title: str,
    start_iso: str,
    end_iso: str,
    attendees: Optional[list[str]] = None,
    description: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> dict:
    """
    Create a calendar event. This is a write operation — creates a proposed_action for approval.
    start_iso / end_iso: ISO 8601 datetime strings with timezone offset.
    attendees: list of email addresses.
    """
    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return integration

        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="gcal_create_event",
            payload={
                "title": title,
                "start_iso": start_iso,
                "end_iso": end_iso,
                "attendees": attendees or [],
                "description": description,
                "calendar_id": calendar_id or "primary",
            },
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)

    await agent_broadcast(workspace_id, "gcal_create_event", "done", f"Proposed: {title}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": f"Event '{title}' queued for approval in AI Work → Actions.",
    }


@mcp.tool()
async def gcal_list_calendars(workspace_id: str) -> list[dict]:
    """
    List all calendars on the connected Google account.
    Returns [{id, summary, primary, accessRole}].
    """
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "google")
        if isinstance(integration, dict):
            return [integration]
        token = await get_google_access_token(integration, db)

    data = await _cal_get("/users/me/calendarList", token)
    if "error" in data:
        return [data]

    return [
        {
            "id": c.get("id"),
            "summary": c.get("summary"),
            "primary": c.get("primary", False),
            "accessRole": c.get("accessRole"),
        }
        for c in data.get("items", [])
    ]
