"""
Marketing site deploy — Vercel rebuild + optional GitHub slug sync.

After publishing a blog post in Supabase:
- Dynamic sitemap (api/sitemap.xml on Vercel) picks up new URLs automatically.
- Static prerender still needs a Vercel build — triggered via deploy hook and/or
  updating .blog-slugs.json in the site repo.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.integrations import decrypt, require_integration
from db.session import AsyncSessionLocal
from services import blog_service

logger = logging.getLogger("site_deploy")

GH_API = "https://api.github.com"
BLOG_SLUGS_PATH = ".blog-slugs.json"


def _slug_entries_from_posts(posts: list[dict]) -> list[dict]:
    return [
        {
            "path": f"/blog/{p.get('slug') or p.get('id')}",
            "sitemap": {"priority": 0.8, "changefreq": "monthly"},
        }
        for p in posts
    ]


async def fetch_published_slug_entries() -> list[dict] | dict:
    """All published posts as prerender/sitemap slug entries."""
    if not blog_service.is_configured():
        return blog_service.config_error()
    data = await blog_service.list_posts(status="published", limit=50)
    if isinstance(data, dict) and "error" in data:
        return data
    return _slug_entries_from_posts(data)


async def trigger_vercel_deploy() -> dict[str, Any]:
    """POST to Vercel Deploy Hook — starts a fresh production build."""
    hook = (settings.lno_site_vercel_deploy_hook or "").strip()
    if not hook:
        return {
            "ok": False,
            "error": "LNO_SITE_VERCEL_DEPLOY_HOOK not set on API server",
        }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(hook)
        ok = resp.status_code in (200, 201, 202)
        body_preview = (resp.text or "")[:300]
        if not ok:
            return {
                "ok": False,
                "status": resp.status_code,
                "error": body_preview or "Vercel deploy hook failed",
            }
        logger.info("Vercel deploy hook triggered (%s)", resp.status_code)
        return {
            "ok": True,
            "status": resp.status_code,
            "message": "Vercel production deploy started",
            "detail": body_preview,
        }
    except Exception as e:
        logger.exception("Vercel deploy hook error")
        return {"ok": False, "error": str(e)}


async def sync_blog_slugs_to_github(
    token: str,
    repo: Optional[str] = None,
    branch: Optional[str] = None,
) -> dict[str, Any]:
    """
    Commit .blog-slugs.json to the marketing site repo via GitHub Contents API.
    repo: owner/name (defaults to LNO_SITE_GITHUB_REPO).
    """
    repo = (repo or settings.lno_site_github_repo or "").strip()
    branch = (branch or settings.lno_site_github_branch or "main").strip()
    if not repo or "/" not in repo:
        return {"ok": False, "error": "LNO_SITE_GITHUB_REPO not set (e.g. your-org/your-site-repo)"}

    entries = await fetch_published_slug_entries()
    if isinstance(entries, dict) and "error" in entries:
        return {"ok": False, "error": entries["error"]}

    content = json.dumps(entries, indent=2) + "\n"
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            get_resp = await client.get(
                f"{GH_API}/repos/{repo}/contents/{BLOG_SLUGS_PATH}",
                headers=headers,
                params={"ref": branch},
            )
            sha: Optional[str] = None
            if get_resp.status_code == 200:
                sha = get_resp.json().get("sha")

            put_body: dict[str, Any] = {
                "message": "chore(seo): sync published blog slugs [lno-os]",
                "content": b64,
                "branch": branch,
            }
            if sha:
                put_body["sha"] = sha

            put_resp = await client.put(
                f"{GH_API}/repos/{repo}/contents/{BLOG_SLUGS_PATH}",
                headers=headers,
                json=put_body,
            )

        if put_resp.status_code not in (200, 201):
            return {
                "ok": False,
                "status": put_resp.status_code,
                "error": (put_resp.text or "")[:500],
            }

        commit = put_resp.json().get("commit", {})
        return {
            "ok": True,
            "repo": repo,
            "branch": branch,
            "slug_count": len(entries),
            "commit_sha": commit.get("sha"),
            "html_url": commit.get("html_url"),
        }
    except Exception as e:
        logger.exception("GitHub slug sync failed")
        return {"ok": False, "error": str(e)}


async def github_token_for_workspace(
    db: AsyncSession, workspace_id: str
) -> tuple[Optional[str], Optional[dict]]:
    integration = await require_integration(db, workspace_id, "github")
    if isinstance(integration, dict):
        return None, integration
    return decrypt(integration.access_token), None


async def redeploy_lno_site(
    db: AsyncSession,
    workspace_id: str,
    *,
    sync_github: bool = True,
) -> dict[str, Any]:
    """
    Full site refresh: optional GitHub slug commit, then Vercel deploy hook.
    """
    result: dict[str, Any] = {"steps": []}

    if sync_github:
        token, err = await github_token_for_workspace(db, workspace_id)
        if err:
            result["steps"].append({"github_sync": err})
        elif token:
            gh = await sync_blog_slugs_to_github(token)
            result["steps"].append({"github_sync": gh})
        else:
            pat = (settings.lno_site_github_pat or "").strip()
            if pat:
                gh = await sync_blog_slugs_to_github(pat)
                result["steps"].append({"github_sync": gh})
            else:
                result["steps"].append({
                    "github_sync": {
                        "ok": False,
                        "skipped": True,
                        "error": "No GitHub integration and LNO_SITE_GITHUB_PAT not set",
                    }
                })

    vercel = await trigger_vercel_deploy()
    result["steps"].append({"vercel_deploy": vercel})
    result["ok"] = vercel.get("ok", False)
    return result


async def after_blog_publish(workspace_id: str) -> dict[str, Any]:
    """Called after a post is published — auto-redeploy if configured."""
    if not settings.lno_site_auto_deploy_on_publish:
        return {"skipped": True, "reason": "lno_site_auto_deploy_on_publish is false"}

    hook = (settings.lno_site_vercel_deploy_hook or "").strip()
    pat = (settings.lno_site_github_pat or "").strip()
    if not hook and not pat:
        return {
            "skipped": True,
            "reason": "No LNO_SITE_VERCEL_DEPLOY_HOOK or LNO_SITE_GITHUB_PAT configured",
        }

    async with AsyncSessionLocal() as db:
        return await redeploy_lno_site(
            db,
            workspace_id,
            sync_github=bool(pat or settings.lno_site_github_repo),
        )
