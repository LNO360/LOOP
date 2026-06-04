"""
Google Search Console service — shared by MCP tools and SEO REST API.
"""
from __future__ import annotations

from urllib.parse import quote
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.integrations import require_integration, get_google_access_token

WEBMASTERS_BASE = "https://www.googleapis.com/webmasters/v3"
INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


async def _gsc_request(method: str, url: str, token: str, json: dict | None = None) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=json,
            timeout=20,
        )
    if resp.status_code == 401:
        return {"error": "Google token expired. Reconnect at AI Work → Settings → Integrations."}
    if resp.status_code == 403:
        return {
            "error": "Search Console access denied. Make sure the connected Google account "
                     "is a verified owner/user of this property, and that the connection was "
                     "re-authorized after Search Console was enabled (reconnect Google)."
        }
    resp.raise_for_status()
    return resp.json()


async def _get_token(db: AsyncSession, workspace_id: str) -> tuple[str | None, dict | None]:
    integration = await require_integration(db, workspace_id, "google")
    if isinstance(integration, dict):
        return None, integration
    token = await get_google_access_token(integration, db)
    return token, None


async def list_sites(db: AsyncSession, workspace_id: str) -> list[dict]:
    token, err = await _get_token(db, workspace_id)
    if err:
        return [err]

    data = await _gsc_request("GET", f"{WEBMASTERS_BASE}/sites", token)
    if "error" in data:
        return [data]

    return [
        {"siteUrl": s.get("siteUrl"), "permissionLevel": s.get("permissionLevel")}
        for s in data.get("siteEntry", [])
    ]


async def search_analytics(
    db: AsyncSession,
    workspace_id: str,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: Optional[list[str]] = None,
    search_type: str = "web",
    row_limit: int = 25,
    start_row: int = 0,
) -> dict:
    token, err = await _get_token(db, workspace_id)
    if err:
        return err

    body = {
        "startDate": start_date,
        "endDate": end_date,
        "type": search_type,
        "rowLimit": max(1, min(row_limit, 25000)),
        "startRow": max(0, start_row),
    }
    if dimensions:
        body["dimensions"] = dimensions

    url = f"{WEBMASTERS_BASE}/sites/{quote(site_url, safe='')}/searchAnalytics/query"
    data = await _gsc_request("POST", url, token, json=body)
    if "error" in data:
        return data

    rows = [
        {
            "keys": r.get("keys", []),
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0), 4),
            "position": round(r.get("position", 0), 2),
        }
        for r in data.get("rows", [])
    ]
    return {
        "site_url": site_url,
        "start_date": start_date,
        "end_date": end_date,
        "dimensions": dimensions or [],
        "rows": rows,
    }


async def list_sitemaps(db: AsyncSession, workspace_id: str, site_url: str) -> list[dict]:
    token, err = await _get_token(db, workspace_id)
    if err:
        return [err]

    url = f"{WEBMASTERS_BASE}/sites/{quote(site_url, safe='')}/sitemaps"
    data = await _gsc_request("GET", url, token)
    if "error" in data:
        return [data]

    return [
        {
            "path": s.get("path"),
            "lastSubmitted": s.get("lastSubmitted"),
            "isPending": s.get("isPending"),
            "errors": s.get("errors"),
            "warnings": s.get("warnings"),
            "contents": s.get("contents"),
        }
        for s in data.get("sitemap", [])
    ]


async def inspect_url(
    db: AsyncSession,
    workspace_id: str,
    site_url: str,
    inspection_url: str,
    language_code: str = "en-US",
) -> dict:
    token, err = await _get_token(db, workspace_id)
    if err:
        return err

    body = {
        "inspectionUrl": inspection_url,
        "siteUrl": site_url,
        "languageCode": language_code,
    }
    data = await _gsc_request("POST", INSPECTION_URL, token, json=body)
    if "error" in data:
        return data

    result = data.get("inspectionResult", {})
    index = result.get("indexStatusResult", {})
    return {
        "inspection_url": inspection_url,
        "verdict": index.get("verdict"),
        "coverageState": index.get("coverageState"),
        "lastCrawlTime": index.get("lastCrawlTime"),
        "googleCanonical": index.get("googleCanonical"),
        "userCanonical": index.get("userCanonical"),
        "robotsTxtState": index.get("robotsTxtState"),
        "indexingState": index.get("indexingState"),
        "mobileUsability": result.get("mobileUsabilityResult", {}).get("verdict"),
        "richResults": result.get("richResultsResult", {}).get("verdict"),
        "inspectionResultLink": result.get("inspectionResultLink"),
    }
