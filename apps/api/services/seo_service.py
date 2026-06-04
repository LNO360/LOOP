"""
SEO aggregation service — overview dashboard data.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.integrations import get_integration
from services import blog_service, gsc_service


def _date_range(days: int) -> tuple[str, str]:
    end = date.today() - timedelta(days=3)  # GSC data lags ~2-3 days
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


async def _blog_health() -> dict:
    if not blog_service.is_configured():
        return {"available": False, "reason": "Blog CMS not configured (LNO_SITE_SUPABASE_URL missing)"}

    posts = await blog_service.list_posts_with_audits(status="all", limit=50)
    if isinstance(posts, dict) and "error" in posts:
        return {"available": False, "reason": posts["error"]}

    if not posts:
        return {
            "available": True,
            "total_posts": 0,
            "draft_count": 0,
            "published_count": 0,
            "avg_score": 0,
            "posts_needing_fixes": 0,
        }

    scores = [p["score"] for p in posts]
    draft_count = sum(1 for p in posts if p.get("status") == "draft")
    return {
        "available": True,
        "total_posts": len(posts),
        "draft_count": draft_count,
        "published_count": len(posts) - draft_count,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "posts_needing_fixes": sum(1 for s in scores if s < 70),
    }


async def _gsc_section(
    db: AsyncSession,
    workspace_id: str,
    site_url: Optional[str],
    days: int,
) -> dict:
    google = await get_integration(db, workspace_id, "google")
    if not google:
        return {"available": False, "reason": "Google not connected"}

    if not site_url:
        return {"available": False, "reason": "No Search Console property selected"}

    start_date, end_date = _date_range(days)

    totals = await gsc_service.search_analytics(
        db, workspace_id, site_url, start_date, end_date,
    )
    if "error" in totals:
        return {"available": False, "reason": totals["error"]}

    total_rows = totals.get("rows") or []
    if total_rows:
        clicks = total_rows[0].get("clicks", 0)
        impressions = total_rows[0].get("impressions", 0)
        ctr = total_rows[0].get("ctr", 0)
        position = total_rows[0].get("position", 0)
    else:
        clicks = impressions = ctr = position = 0

    top_queries = await gsc_service.search_analytics(
        db, workspace_id, site_url, start_date, end_date,
        dimensions=["query"], row_limit=5,
    )
    top_pages = await gsc_service.search_analytics(
        db, workspace_id, site_url, start_date, end_date,
        dimensions=["page"], row_limit=5,
    )

    sitemaps = await gsc_service.list_sitemaps(db, workspace_id, site_url)
    sitemap_errors = 0
    sitemap_warnings = 0
    if sitemaps and "error" not in sitemaps[0]:
        for sm in sitemaps:
            sitemap_errors += int(sm.get("errors") or 0)
            sitemap_warnings += int(sm.get("warnings") or 0)

    return {
        "available": True,
        "site_url": site_url,
        "start_date": start_date,
        "end_date": end_date,
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "avg_position": position,
        "top_queries": top_queries.get("rows", []) if "error" not in top_queries else [],
        "top_pages": top_pages.get("rows", []) if "error" not in top_pages else [],
        "sitemap_errors": sitemap_errors,
        "sitemap_warnings": sitemap_warnings,
    }


async def get_overview(
    db: AsyncSession,
    workspace_id: str,
    site_url: Optional[str] = None,
    days: int = 28,
) -> dict:
    google = await get_integration(db, workspace_id, "google")
    gsc = await _gsc_section(db, workspace_id, site_url, days)
    blog = await _blog_health()

    return {
        "google_connected": google is not None,
        "blog_configured": blog_service.is_configured(),
        "gsc": gsc,
        "blog": blog,
    }
