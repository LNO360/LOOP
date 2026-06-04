"""Execute approved GitHub proposed actions (create issue, add comment)."""
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.integrations import get_integration, decrypt
from core.github_scope import enforce_repo_org

GH_API = "https://api.github.com"


async def _github_token(db: AsyncSession, workspace_id: str) -> str:
    row = await get_integration(db, workspace_id, "github")
    if not row:
        raise ValueError(
            "GitHub not connected. Connect at AI Work → Settings → Integrations."
        )
    return decrypt(row.access_token)


async def _gh_post(path: str, token: str, body: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GH_API}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"GitHub API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


async def _gh_patch(path: str, token: str, body: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{GH_API}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=15,
        )
    if resp.status_code >= 400:
        raise ValueError(f"GitHub API error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


async def execute_github_create_issue(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Create a GitHub issue after human approval."""
    token = await _github_token(db, workspace_id)
    repo = payload["repo"]
    if err := enforce_repo_org(repo):
        raise ValueError(err["error"])
    body: dict = {"title": payload["title"]}
    if payload.get("body"):
        body["body"] = payload["body"]
    if payload.get("labels"):
        body["labels"] = payload["labels"]
    if payload.get("assignees"):
        body["assignees"] = payload["assignees"]

    data = await _gh_post(f"/repos/{repo}/issues", token, body)
    return {
        "issue_number": data.get("number"),
        "title": data.get("title"),
        "html_url": data.get("html_url"),
    }


async def execute_github_add_issue_comment(
    db: AsyncSession,
    workspace_id: str,
    payload: dict,
) -> dict:
    """Add a comment to a GitHub issue after human approval."""
    token = await _github_token(db, workspace_id)
    repo = payload["repo"]
    if err := enforce_repo_org(repo):
        raise ValueError(err["error"])
    issue_number = payload["issue_number"]
    data = await _gh_post(
        f"/repos/{repo}/issues/{issue_number}/comments",
        token,
        {"body": payload["comment_body"]},
    )
    return {
        "comment_id": data.get("id"),
        "html_url": data.get("html_url"),
    }
