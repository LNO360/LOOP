"""
MCP tools for your marketing site marketing site deploy (Vercel + GitHub prerender sync).

Sitemap URLs are served dynamically from Supabase after the site ships api/sitemap.xml.
This tool rebuilds static HTML (prerender) and refreshes .blog-slugs.json in the site repo.

GSC sitemap *submission* is still read-only via gsc_* tools — resubmit in Search Console
or use URL Inspection after redeploy.
"""
from typing import Optional

from mcp_server.helpers import propose_destructive_action
from mcp_server.server import mcp, agent_broadcast
from core.config import settings
from services import blog_service, site_deploy_service


@mcp.tool()
async def lno_site_list_published_urls(workspace_id: str, limit: int = 50) -> dict:
    """
    List published blog URLs that should appear on your marketing site/sitemap.xml and in prerender.
    Use after publishing posts to verify slugs before redeploying the site.
    """
    if not blog_service.is_configured():
        return blog_service.config_error()

    await agent_broadcast(workspace_id, "lno_site_list_published_urls", "running")
    entries = await site_deploy_service.fetch_published_slug_entries()
    if isinstance(entries, dict) and "error" in entries:
        await agent_broadcast(workspace_id, "lno_site_list_published_urls", "error", entries["error"])
        return entries

    base_url = (settings.lno_site_supabase_url or "https://your-domain.com").rstrip("/")
    urls = [f"{base_url}{e['path']}" for e in entries[:limit]]
    await agent_broadcast(
        workspace_id,
        "lno_site_list_published_urls",
        "done",
        f"{len(urls)} URLs",
    )
    return {
        "count": len(urls),
        "urls": urls,
        "note": (
            "Dynamic sitemap at https://your marketing site/sitemap.xml updates without a git commit "
            "once api/sitemap.xml is deployed. Static HTML still needs lno_site_redeploy."
        ),
    }


@mcp.tool()
async def lno_site_redeploy(
    workspace_id: str,
    sync_github: bool = True,
    run_id: Optional[str] = None,
) -> dict:
    """
    Queue a production redeploy of your marketing site (requires human approval).

    Steps when approved:
    1. Optionally commit .blog-slugs.json to the marketing site GitHub repo (all published posts).
    2. Trigger Vercel Deploy Hook so the site rebuilds prerendered /blog/* pages.

    Requires workspace GitHub connected (for slug sync) and LNO_SITE_VERCEL_DEPLOY_HOOK
    on the API server. After deploy, remind the user to resubmit the sitemap in GSC if needed.

    sync_github: if true, update .blog-slugs.json in the site repo before deploy (default true).
    """
    await agent_broadcast(workspace_id, "lno_site_redeploy", "running")

    if not (settings.lno_site_vercel_deploy_hook or "").strip():
        err = {
            "error": (
                "LNO_SITE_VERCEL_DEPLOY_HOOK not configured on API. "
                "Add it in .env.prod (Vercel → Settings → Deploy Hooks)."
            )
        }
        await agent_broadcast(workspace_id, "lno_site_redeploy", "error", err["error"])
        return err

    result = await propose_destructive_action(
        workspace_id,
        "lno_site_redeploy",
        {"sync_github": sync_github},
        risk_level="medium",
        run_id=run_id,
        summary="Redeploy your marketing site (Vercel build + optional GitHub slug sync)",
    )
    await agent_broadcast(workspace_id, "lno_site_redeploy", "done", "queued")
    return result
