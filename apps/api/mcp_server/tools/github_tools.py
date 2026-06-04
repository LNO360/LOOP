"""
GitHub MCP tools (workspace-level GitHub OAuth).

github_list_repos            — list accessible repos
github_list_issues           — issues for a repo
github_get_issue             — full issue + comments summary
github_list_prs              — open PRs with review status
github_get_pr                — PR stats + checks (no full diff)
github_search_code           — code search (rate-limit aware)
github_create_issue          — proposed_action (medium risk)
github_add_issue_comment     — proposed_action (low risk)
"""
import uuid
from typing import Optional

import httpx
from db.session import AsyncSessionLocal
from mcp_server.server import mcp, agent_broadcast
from core.integrations import require_integration
from core.github_scope import enforce_repo_org, resolve_list_org, scope_code_search_query

GH_API = "https://api.github.com"
GH_SEARCH = "https://api.github.com/search"


async def _gh_token(integration) -> str:
    """Decrypt and return the GitHub access token."""
    from core.integrations import decrypt
    return decrypt(integration.access_token)


async def _gh_get(path: str, token: str, params: dict = None) -> dict | list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GH_API}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params=params or {},
            timeout=15,
        )
    if resp.status_code == 401:
        return {"error": "GitHub token expired or revoked. Reconnect at AI Work → Settings → Integrations."}
    if resp.status_code == 403:
        return {"error": f"GitHub rate limit or permission denied: {resp.text[:200]}"}
    if resp.status_code >= 400:
        return {"error": f"GitHub API error {resp.status_code}: {resp.text[:300]}"}
    return resp.json()


@mcp.tool()
async def github_list_repos(
    workspace_id: str,
    org: Optional[str] = None,
    max_results: int = 10,
) -> list[dict]:
    """
    List GitHub repos for the connected account.
    org: filter by organization (optional). If GITHUB_DEFAULT_ORG is set in server env,
    only that organization's repos are returned (personal repos are excluded).
    Returns [{id, full_name, description, private, default_branch, updated_at, open_issues_count}].
    """
    list_org, org_err = resolve_list_org(org)
    if org_err:
        return [org_err]

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return [integration]
        token = await _gh_token(integration)

    await agent_broadcast(workspace_id, "github_list_repos", "running")
    if list_org:
        data = await _gh_get(
            f"/orgs/{list_org}/repos",
            token,
            {"per_page": min(max_results, 100), "sort": "updated"},
        )
    else:
        data = await _gh_get(
            "/user/repos",
            token,
            {
                "per_page": min(max_results, 100),
                "sort": "updated",
                "affiliation": "owner,collaborator,organization_member",
            },
        )

    if isinstance(data, dict) and "error" in data:
        return [data]

    repos = data[:max_results] if isinstance(data, list) else []
    await agent_broadcast(workspace_id, "github_list_repos", "done", f"{len(repos)} repos")
    return [
        {
            "id": r["id"],
            "full_name": r["full_name"],
            "description": r.get("description"),
            "private": r.get("private"),
            "default_branch": r.get("default_branch"),
            "updated_at": r.get("updated_at"),
            "open_issues_count": r.get("open_issues_count"),
            "html_url": r.get("html_url"),
        }
        for r in repos
    ]


@mcp.tool()
async def github_list_issues(
    workspace_id: str,
    repo: str,
    state: str = "open",
    label: Optional[str] = None,
    assignee: Optional[str] = None,
    max_results: int = 10,
) -> list[dict]:
    """
    List GitHub issues for a repo.
    repo: 'owner/repo' format.
    state: 'open' | 'closed' | 'all'.
    Returns [{number, title, state, labels, assignees, created_at, updated_at, html_url}].
    """
    if err := enforce_repo_org(repo):
        return [err]

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return [integration]
        token = await _gh_token(integration)

    params = {"state": state, "per_page": min(max_results, 100)}
    if label:
        params["labels"] = label
    if assignee:
        params["assignee"] = assignee

    data = await _gh_get(f"/repos/{repo}/issues", token, params)
    if isinstance(data, dict) and "error" in data:
        return [data]

    # Filter out PRs (GitHub issues API returns PRs too)
    issues = [i for i in (data or []) if "pull_request" not in i][:max_results]
    await agent_broadcast(workspace_id, "github_list_issues", "done", f"{len(issues)} issues in {repo}")
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "labels": [lb["name"] for lb in i.get("labels", [])],
            "assignees": [a["login"] for a in i.get("assignees", [])],
            "created_at": i.get("created_at"),
            "updated_at": i.get("updated_at"),
            "html_url": i.get("html_url"),
        }
        for i in issues
    ]


@mcp.tool()
async def github_get_issue(
    workspace_id: str,
    repo: str,
    issue_number: int,
) -> dict:
    """
    Get full details of a GitHub issue including comment summary.
    repo: 'owner/repo'. Returns {number, title, body, state, labels, assignees, comments_summary}.
    """
    if err := enforce_repo_org(repo):
        return err

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return integration
        token = await _gh_token(integration)

    issue = await _gh_get(f"/repos/{repo}/issues/{issue_number}", token)
    if isinstance(issue, dict) and "error" in issue:
        return issue

    comments_data = await _gh_get(f"/repos/{repo}/issues/{issue_number}/comments", token, {"per_page": 10})
    comments_summary = []
    if isinstance(comments_data, list):
        for c in comments_data[:5]:
            comments_summary.append({
                "author": c.get("user", {}).get("login"),
                "body": (c.get("body") or "")[:300],
                "created_at": c.get("created_at"),
            })

    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "body": (issue.get("body") or "")[:1000],
        "state": issue.get("state"),
        "labels": [lb["name"] for lb in issue.get("labels", [])],
        "assignees": [a["login"] for a in issue.get("assignees", [])],
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "html_url": issue.get("html_url"),
        "comments_count": issue.get("comments"),
        "comments_summary": comments_summary,
    }


@mcp.tool()
async def github_list_prs(
    workspace_id: str,
    repo: str,
    state: str = "open",
    max_results: int = 10,
) -> list[dict]:
    """
    List pull requests for a repo.
    repo: 'owner/repo'. state: 'open' | 'closed' | 'all'.
    Returns [{number, title, state, draft, author, head_branch, base_branch, created_at, html_url}].
    """
    if err := enforce_repo_org(repo):
        return [err]

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return [integration]
        token = await _gh_token(integration)

    data = await _gh_get(f"/repos/{repo}/pulls", token, {"state": state, "per_page": min(max_results, 100)})
    if isinstance(data, dict) and "error" in data:
        return [data]

    prs = (data or [])[:max_results]
    await agent_broadcast(workspace_id, "github_list_prs", "done", f"{len(prs)} PRs in {repo}")
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "draft": pr.get("draft", False),
            "author": pr.get("user", {}).get("login"),
            "head_branch": pr.get("head", {}).get("ref"),
            "base_branch": pr.get("base", {}).get("ref"),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "html_url": pr.get("html_url"),
            "review_comments": pr.get("review_comments"),
        }
        for pr in prs
    ]


@mcp.tool()
async def github_get_pr(
    workspace_id: str,
    repo: str,
    pr_number: int,
) -> dict:
    """
    Get PR details: diff stats, files changed, CI checks status.
    repo: 'owner/repo'. Returns {number, title, body, stats, files_changed, checks}.
    Does NOT return full diff — only file paths and line counts.
    """
    if err := enforce_repo_org(repo):
        return err

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return integration
        token = await _gh_token(integration)

    pr = await _gh_get(f"/repos/{repo}/pulls/{pr_number}", token)
    if isinstance(pr, dict) and "error" in pr:
        return pr

    # Get changed files (capped at 30)
    files_data = await _gh_get(f"/repos/{repo}/pulls/{pr_number}/files", token, {"per_page": 30})
    files = []
    if isinstance(files_data, list):
        files = [
            {"filename": f.get("filename"), "status": f.get("status"), "additions": f.get("additions"), "deletions": f.get("deletions")}
            for f in files_data[:30]
        ]

    # Get check runs
    sha = pr.get("head", {}).get("sha", "")
    checks_summary = []
    if sha:
        checks_data = await _gh_get(f"/repos/{repo}/commits/{sha}/check-runs", token, {"per_page": 10})
        if isinstance(checks_data, dict) and "check_runs" in checks_data:
            for cr in checks_data["check_runs"][:10]:
                checks_summary.append({
                    "name": cr.get("name"),
                    "status": cr.get("status"),
                    "conclusion": cr.get("conclusion"),
                })

    return {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "body": (pr.get("body") or "")[:2000],
        "state": pr.get("state"),
        "draft": pr.get("draft"),
        "author": pr.get("user", {}).get("login"),
        "head_branch": pr.get("head", {}).get("ref"),
        "base_branch": pr.get("base", {}).get("ref"),
        "stats": {
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "changed_files": pr.get("changed_files"),
        },
        "files_changed": files,
        "checks": checks_summary,
        "html_url": pr.get("html_url"),
    }


@mcp.tool()
async def github_search_code(
    workspace_id: str,
    query: str,
    repo: Optional[str] = None,
    max_results: int = 10,
) -> list[dict]:
    """
    Search code on GitHub.
    query: search string (GitHub code search syntax).
    repo: optional 'owner/repo' to scope to one repo.
    Returns [{repository, path, html_url, text_matches_snippet}].
    Rate-limited: GitHub allows ~10 code search requests/min unauthenticated, 30/min authenticated.
    """
    full_query, scope_err = scope_code_search_query(query, repo)
    if scope_err:
        return [scope_err]

    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return [integration]
        token = await _gh_token(integration)

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GH_SEARCH}/code",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.text-match+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"q": full_query, "per_page": min(max_results, 30)},
            timeout=15,
        )

    if resp.status_code == 403:
        return [{"error": "GitHub search rate limit hit. Wait 1 minute and retry."}]
    if resp.status_code >= 400:
        return [{"error": f"GitHub search error {resp.status_code}: {resp.text[:300]}"}]

    items = resp.json().get("items", [])[:max_results]
    await agent_broadcast(workspace_id, "github_search_code", "done", f"{len(items)} results for: {query}")
    return [
        {
            "repository": item.get("repository", {}).get("full_name"),
            "path": item.get("path"),
            "html_url": item.get("html_url"),
            "snippet": (item.get("text_matches") or [{}])[0].get("fragment", "")[:300] if item.get("text_matches") else "",
        }
        for item in items
    ]


@mcp.tool()
async def github_create_issue(
    workspace_id: str,
    repo: str,
    title: str,
    body: Optional[str] = None,
    labels: Optional[list[str]] = None,
    assignees: Optional[list[str]] = None,
) -> dict:
    """
    Create a GitHub issue. Write operation — creates proposed_action for human approval.
    repo: 'owner/repo'.
    """
    if err := enforce_repo_org(repo):
        return err

    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return integration

        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="github_create_issue",
            payload={
                "repo": repo,
                "title": title,
                "body": body,
                "labels": labels or [],
                "assignees": assignees or [],
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
            action_type="github_create_issue",
            payload={"repo": repo, "title": title},
        )

    await agent_broadcast(workspace_id, "github_create_issue", "done", f"Proposed: issue in {repo}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": f"Issue '{title}' in {repo} queued for approval in AI Work → Actions.",
    }


@mcp.tool()
async def github_add_issue_comment(
    workspace_id: str,
    repo: str,
    issue_number: int,
    comment_body: str,
) -> dict:
    """
    Add a comment to a GitHub issue or PR. Write operation — creates proposed_action for approval.
    repo: 'owner/repo'.
    """
    if err := enforce_repo_org(repo):
        return err

    from models.agent import ProposedAction
    async with AsyncSessionLocal() as db:
        integration = await require_integration(db, workspace_id, "github")
        if isinstance(integration, dict):
            return integration

        action = ProposedAction(
            workspace_id=uuid.UUID(workspace_id),
            action_type="github_add_issue_comment",
            payload={
                "repo": repo,
                "issue_number": issue_number,
                "comment_body": comment_body,
            },
            risk_level="low",
            status="pending",
        )
        db.add(action)
        await db.commit()
        action_id = str(action.id)
        from core.telegram_notify import notify_proposed_action_created
        await notify_proposed_action_created(
            action_id=action_id,
            action_type="github_add_issue_comment",
            payload={"repo": repo, "issue_number": issue_number, "body_preview": comment_body[:80]},
        )

    await agent_broadcast(workspace_id, "github_add_issue_comment", "done", f"Proposed: comment on {repo}#{issue_number}")
    return {
        "proposed": True,
        "action_id": action_id,
        "message": f"Comment on {repo}#{issue_number} queued for approval in AI Work → Actions.",
    }
