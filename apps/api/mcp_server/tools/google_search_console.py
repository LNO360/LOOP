"""
Google Search Console MCP tools (read-only).
"""
from typing import Optional

from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
from services import gsc_service


@mcp.tool()
async def gsc_list_sites(workspace_id: str) -> list[dict]:
    """
    List Google Search Console properties the connected account can access.
    Returns [{siteUrl, permissionLevel}]. Use the siteUrl values with the other gsc_* tools.
    """
    async with AsyncSessionLocal() as db:
        await agent_broadcast(workspace_id, "gsc_list_sites", "running")
        sites = await gsc_service.list_sites(db, workspace_id)
        if len(sites) == 1 and "error" in sites[0]:
            await agent_broadcast(workspace_id, "gsc_list_sites", "error", sites[0]["error"])
            return sites
        await agent_broadcast(workspace_id, "gsc_list_sites", "done", f"{len(sites)} sites")
        return sites


@mcp.tool()
async def gsc_search_analytics(
    workspace_id: str,
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: Optional[list[str]] = None,
    search_type: str = "web",
    row_limit: int = 25,
    start_row: int = 0,
) -> dict:
    """
    Query Search Console search performance for a property.
    Returns {site_url, rows: [{keys, clicks, impressions, ctr, position}], ...}.
    """
    async with AsyncSessionLocal() as db:
        await agent_broadcast(workspace_id, "gsc_search_analytics", "running", site_url)
        result = await gsc_service.search_analytics(
            db, workspace_id, site_url, start_date, end_date,
            dimensions=dimensions, search_type=search_type,
            row_limit=row_limit, start_row=start_row,
        )
        if "error" in result:
            return result
        await agent_broadcast(workspace_id, "gsc_search_analytics", "done", f"{len(result['rows'])} rows")
        return result


@mcp.tool()
async def gsc_list_sitemaps(workspace_id: str, site_url: str) -> list[dict]:
    """
    List sitemaps submitted for a Search Console property.
    Returns [{path, lastSubmitted, isPending, errors, warnings, contents}].
    """
    async with AsyncSessionLocal() as db:
        return await gsc_service.list_sitemaps(db, workspace_id, site_url)


@mcp.tool()
async def gsc_inspect_url(
    workspace_id: str,
    site_url: str,
    inspection_url: str,
    language_code: str = "en-US",
) -> dict:
    """
    Inspect a single URL's index status in Google (URL Inspection API).
    """
    async with AsyncSessionLocal() as db:
        await agent_broadcast(workspace_id, "gsc_inspect_url", "running", inspection_url)
        result = await gsc_service.inspect_url(
            db, workspace_id, site_url, inspection_url, language_code=language_code,
        )
        if "error" in result:
            return result
        await agent_broadcast(
            workspace_id, "gsc_inspect_url", "done",
            result.get("coverageState", "inspected"),
        )
        return result
