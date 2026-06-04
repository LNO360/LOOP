"""
SEO REST API — Search Console analytics, blog audits, URL inspection.

Base: /api/v1/workspaces/{workspace_id}/seo
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from db.session import get_db
from models import User
from services import blog_service, gsc_service, seo_service

router = APIRouter(
    prefix="/workspaces/{workspace_id}/seo",
    tags=["seo"],
)


def _blog_unavailable(result: dict) -> None:
    if isinstance(result, dict) and "error" in result:
        if "not configured" in result["error"].lower():
            raise HTTPException(503, result["error"])
        raise HTTPException(400, result["error"])


class InspectUrlRequest(BaseModel):
    site_url: str
    inspection_url: str
    language_code: str = "en-US"


class UpdateBlogPostRequest(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    category: Optional[str] = None
    meta_description: Optional[str] = None
    tags: Optional[list[str]] = None
    cover_image_url: Optional[str] = None


@router.get("/overview")
async def get_overview(
    workspace_id: str,
    site_url: Optional[str] = Query(None),
    days: int = Query(28, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await seo_service.get_overview(db, workspace_id, site_url=site_url, days=days)


@router.get("/gsc/sites")
async def list_gsc_sites(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sites = await gsc_service.list_sites(db, workspace_id)
    if len(sites) == 1 and "error" in sites[0]:
        raise HTTPException(400, sites[0]["error"])
    return {"sites": sites}


@router.get("/gsc/analytics")
async def get_gsc_analytics(
    workspace_id: str,
    site_url: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    dimensions: Optional[str] = Query(None, description="Comma-separated: query,page,country,device,date"),
    row_limit: int = Query(25, ge=1, le=250),
    start_row: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dims = [d.strip() for d in dimensions.split(",") if d.strip()] if dimensions else None
    result = await gsc_service.search_analytics(
        db, workspace_id, site_url, start_date, end_date,
        dimensions=dims, row_limit=row_limit, start_row=start_row,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/gsc/sitemaps")
async def get_gsc_sitemaps(
    workspace_id: str,
    site_url: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sitemaps = await gsc_service.list_sitemaps(db, workspace_id, site_url)
    if len(sitemaps) == 1 and "error" in sitemaps[0]:
        raise HTTPException(400, sitemaps[0]["error"])
    return {"sitemaps": sitemaps}


@router.post("/gsc/inspect")
async def inspect_url(
    workspace_id: str,
    body: InspectUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await gsc_service.inspect_url(
        db, workspace_id, body.site_url, body.inspection_url,
        language_code=body.language_code,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/blog/posts")
async def list_blog_posts(
    workspace_id: str,
    status: str = Query("all"),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=50),
    include_audit: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not blog_service.is_configured():
        raise HTTPException(503, blog_service.config_error()["error"])

    if include_audit:
        result = await blog_service.list_posts_with_audits(status=status, category=category, limit=limit)
    else:
        result = await blog_service.list_posts(status=status, category=category, limit=limit)

    if isinstance(result, dict) and "error" in result:
        _blog_unavailable(result)
    return {"posts": result}


@router.get("/blog/posts/{post_id}")
async def get_blog_post(
    workspace_id: str,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await blog_service.get_post(post_id)
    if "error" in result:
        _blog_unavailable(result)
    return result


@router.get("/blog/posts/{post_id}/audit")
async def audit_blog_post(
    workspace_id: str,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await blog_service.run_seo_audit(post_id)
    if "error" in result:
        _blog_unavailable(result)
    return result


@router.patch("/blog/posts/{post_id}")
async def update_blog_post(
    workspace_id: str,
    post_id: str,
    body: UpdateBlogPostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await blog_service.update_post(
        post_id=post_id,
        title=body.title,
        slug=body.slug,
        excerpt=body.excerpt,
        category=body.category,
        meta_description=body.meta_description,
        tags=body.tags,
        cover_image_url=body.cover_image_url,
    )
    if "error" in result:
        _blog_unavailable(result)
    return result


@router.post("/blog/posts/{post_id}/publish")
async def propose_blog_publish(
    workspace_id: str,
    post_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await blog_service.propose_publish(workspace_id, post_id)
    if "error" in result:
        _blog_unavailable(result)
    return result
