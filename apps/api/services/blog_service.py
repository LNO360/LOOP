"""
Blog CMS service for the marketing site — shared by MCP tools and SEO REST API.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from core.config import settings
from db.session import AsyncSessionLocal
from models.agent import ProposedAction


def is_configured() -> bool:
    return bool(settings.lno_site_supabase_url and settings.lno_site_supabase_service_key)


def config_error() -> dict:
    return {"error": "LNO_SITE_SUPABASE_URL not configured"}


def _sb_headers() -> dict:
    key = settings.lno_site_supabase_service_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _sb_url(path: str) -> str:
    return f"{settings.lno_site_supabase_url.rstrip('/')}/rest/v1/{path}"


async def _sb_get(path: str, params: dict | None = None) -> list[dict] | dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_sb_url(path), headers=_sb_headers(), params=params or {})
    if resp.status_code == 401:
        return {"error": "Supabase auth failed. Check LNO_SITE_SUPABASE_SERVICE_KEY."}
    resp.raise_for_status()
    return resp.json()


async def _sb_post(path: str, body: dict) -> list[dict] | dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_sb_url(path), headers=_sb_headers(), json=body)
    if resp.status_code == 401:
        return {"error": "Supabase auth failed. Check LNO_SITE_SUPABASE_SERVICE_KEY."}
    resp.raise_for_status()
    data = resp.json()
    return data[0] if isinstance(data, list) and data else data


async def _sb_patch(path: str, params: dict, body: dict) -> list[dict] | dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.patch(
            _sb_url(path), headers=_sb_headers(), params=params, json=body
        )
    if resp.status_code == 401:
        return {"error": "Supabase auth failed. Check LNO_SITE_SUPABASE_SERVICE_KEY."}
    resp.raise_for_status()
    data = resp.json()
    return data[0] if isinstance(data, list) and data else data


def extract_text(node: dict) -> str:
    """Recursively extract plain text from a TipTap JSON node."""
    if not isinstance(node, dict):
        return ""
    text = node.get("text", "")
    for child in node.get("content", []):
        text += " " + extract_text(child)
    return text


def seo_audit(post: dict) -> dict:
    title = post.get("title") or ""
    meta = post.get("meta_description") or ""
    excerpt = post.get("excerpt") or ""
    tags = post.get("tags") or []
    cover = post.get("cover_image_url") or ""
    slug = post.get("slug") or ""
    content = post.get("content") or {}

    word_count = len(extract_text(content).split()) if content else 0

    issues = []
    score = 0

    if title and 10 <= len(title) <= 60:
        score += 20
    elif not title:
        issues.append("title missing")
    elif len(title) > 60:
        issues.append(f"title too long ({len(title)} chars, max 60)")
        score += 10
    else:
        issues.append(f"title too short ({len(title)} chars, min 10)")
        score += 10

    if meta and 50 <= len(meta) <= 160:
        score += 25
    elif not meta:
        issues.append("meta_description missing")
    elif len(meta) < 50:
        issues.append(f"meta_description too short ({len(meta)} chars, min 50)")
        score += 10
    else:
        issues.append(f"meta_description too long ({len(meta)} chars, max 160)")
        score += 15

    if excerpt:
        score += 15
    else:
        issues.append("excerpt missing")

    if tags:
        score += 15
    else:
        issues.append("no tags set")

    if cover:
        score += 15
    else:
        issues.append("cover image missing")

    if slug:
        score += 10
    else:
        issues.append("slug missing")

    return {
        "post_id": post.get("id"),
        "title_length": len(title),
        "has_meta_description": bool(meta),
        "meta_description_length": len(meta),
        "has_excerpt": bool(excerpt),
        "has_tags": bool(tags),
        "tag_count": len(tags),
        "has_cover_image": bool(cover),
        "has_slug": bool(slug),
        "estimated_word_count": word_count,
        "issues": issues,
        "score": score,
    }


_LIST_SELECT = "id,title,slug,status,category,tags,published_at,updated_at"
_AUDIT_SELECT = (
    "id,title,slug,status,category,tags,published_at,updated_at,"
    "meta_description,excerpt,cover_image_url,content"
)


async def list_posts(
    status: str = "all",
    category: Optional[str] = None,
    limit: int = 20,
) -> list[dict] | dict:
    if not is_configured():
        return config_error()

    params = {
        "select": _LIST_SELECT,
        "order": "updated_at.desc",
        "limit": str(min(limit, 50)),
    }
    if status and status != "all":
        params["status"] = f"eq.{status}"
    if category:
        params["category"] = f"eq.{category}"

    data = await _sb_get("posts", params)
    if isinstance(data, dict) and "error" in data:
        return data
    return data


async def list_posts_with_audits(
    status: str = "all",
    category: Optional[str] = None,
    limit: int = 50,
) -> list[dict] | dict:
    if not is_configured():
        return config_error()

    params = {
        "select": _AUDIT_SELECT,
        "order": "updated_at.desc",
        "limit": str(min(limit, 50)),
    }
    if status and status != "all":
        params["status"] = f"eq.{status}"
    if category:
        params["category"] = f"eq.{category}"

    data = await _sb_get("posts", params)
    if isinstance(data, dict) and "error" in data:
        return data

    result = []
    for post in data:
        audit = seo_audit(post)
        result.append({
            "id": post.get("id"),
            "title": post.get("title"),
            "slug": post.get("slug"),
            "status": post.get("status"),
            "category": post.get("category"),
            "tags": post.get("tags"),
            "published_at": post.get("published_at"),
            "updated_at": post.get("updated_at"),
            "score": audit["score"],
            "issues": audit["issues"],
            "issue_count": len(audit["issues"]),
        })
    return result


async def get_post(post_id: str) -> dict:
    if not is_configured():
        return config_error()

    data = await _sb_get("posts", {"id": f"eq.{post_id}", "select": "*"})
    if isinstance(data, dict) and "error" in data:
        return data
    if not data:
        return {"error": "Post not found", "post_id": post_id}
    return data[0] if isinstance(data, list) else data


async def run_seo_audit(post_id: str) -> dict:
    if not is_configured():
        return config_error()

    data = await _sb_get("posts", {"id": f"eq.{post_id}", "select": "*"})
    if isinstance(data, dict) and "error" in data:
        return data
    if not data:
        return {"error": "Post not found", "post_id": post_id}
    post = data[0] if isinstance(data, list) else data
    return seo_audit(post)


async def create_post(
    title: str,
    content: dict,
    slug: Optional[str] = None,
    excerpt: Optional[str] = None,
    category: str = "operator",
    meta_description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    cover_image_url: Optional[str] = None,
    read_time: Optional[int] = None,
    author_name: Optional[str] = None,
    author_role: Optional[str] = None,
    author_initials: Optional[str] = None,
) -> dict:
    if not is_configured():
        return config_error()

    body: dict = {
        "title": title,
        "content": content,
        "category": category,
        "status": "draft",
    }
    if slug is not None:
        body["slug"] = slug
    if excerpt is not None:
        body["excerpt"] = excerpt
    if meta_description is not None:
        body["meta_description"] = meta_description
    if tags is not None:
        body["tags"] = tags
    if cover_image_url is not None:
        body["cover_image_url"] = cover_image_url
    if read_time is not None:
        body["read_time"] = read_time
    if author_name is not None:
        body["author_name"] = author_name
    if author_role is not None:
        body["author_role"] = author_role
    if author_initials is not None:
        body["author_initials"] = author_initials

    return await _sb_post("posts", body)


async def update_post(
    post_id: str,
    title: Optional[str] = None,
    content: Optional[dict] = None,
    slug: Optional[str] = None,
    excerpt: Optional[str] = None,
    category: Optional[str] = None,
    meta_description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    cover_image_url: Optional[str] = None,
    read_time: Optional[int] = None,
    author_name: Optional[str] = None,
    author_role: Optional[str] = None,
    author_initials: Optional[str] = None,
    featured: Optional[bool] = None,
) -> dict:
    if not is_configured():
        return config_error()

    patch: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if title is not None:
        patch["title"] = title
    if content is not None:
        patch["content"] = content
    if slug is not None:
        patch["slug"] = slug
    if excerpt is not None:
        patch["excerpt"] = excerpt
    if category is not None:
        patch["category"] = category
    if meta_description is not None:
        patch["meta_description"] = meta_description
    if tags is not None:
        patch["tags"] = tags
    if cover_image_url is not None:
        patch["cover_image_url"] = cover_image_url
    if read_time is not None:
        patch["read_time"] = read_time
    if author_name is not None:
        patch["author_name"] = author_name
    if author_role is not None:
        patch["author_role"] = author_role
    if author_initials is not None:
        patch["author_initials"] = author_initials
    if featured is not None:
        patch["featured"] = featured

    if len(patch) == 1:
        return {"error": "No fields to update — pass at least one field besides post_id"}

    return await _sb_patch("posts", {"id": f"eq.{post_id}"}, patch)


async def propose_publish(workspace_id: str, post_id: str) -> dict:
    if not is_configured():
        return config_error()

    data = await _sb_get("posts", {"id": f"eq.{post_id}", "select": "id,title,slug,status"})
    if isinstance(data, dict) and "error" in data:
        return data
    if not data:
        return {"error": "Post not found", "post_id": post_id}
    post = data[0] if isinstance(data, list) else data
    title = post.get("title", post_id)
    slug = post.get("slug", "")

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="lno_blog_publish",
            payload={"post_id": post_id, "title": title, "slug": slug},
            risk_level="medium",
        )
        db.add(action)
        await db.flush()
        action_id = str(action.id)
        await db.commit()

    return {
        "proposed": True,
        "action_id": action_id,
        "action_type": "lno_blog_publish",
        "post_id": post_id,
        "title": title,
        "message": f"Publish '{title}' queued for approval. Approve via LNO OS → Agent → Proposed Actions.",
    }


async def propose_delete(workspace_id: str, post_id: str) -> dict:
    if not is_configured():
        return config_error()

    data = await _sb_get("posts", {"id": f"eq.{post_id}", "select": "id,title,slug"})
    if isinstance(data, dict) and "error" in data:
        return data
    if not data:
        return {"error": "Post not found", "post_id": post_id}
    post = data[0] if isinstance(data, list) else data
    title = post.get("title", post_id)

    async with AsyncSessionLocal() as db:
        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="lno_blog_delete",
            payload={"post_id": post_id, "title": title},
            risk_level="high",
        )
        db.add(action)
        await db.flush()
        action_id = str(action.id)
        await db.commit()

    return {
        "proposed": True,
        "action_id": action_id,
        "action_type": "lno_blog_delete",
        "post_id": post_id,
        "title": title,
        "message": f"Delete '{title}' queued for approval.",
    }
