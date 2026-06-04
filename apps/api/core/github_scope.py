"""GitHub org scoping — limit workspace tools to one organization."""
from typing import Optional

from core.config import settings


def github_allowed_org() -> Optional[str]:
    """Configured org slug (e.g. LNO360). Empty = no restriction (legacy behavior)."""
    org = (settings.github_default_org or "").strip()
    return org or None


def github_org_error() -> dict:
    org = github_allowed_org() or "the configured organization"
    return {
        "error": (
            f"This workspace is restricted to GitHub organization '{org}' only. "
            f"Use repos as '{org}/repo-name' or list repos with github_list_repos."
        )
    }


def enforce_repo_org(repo: str) -> Optional[dict]:
    """
    Return an error dict if repo owner is outside the allowed org.
    repo format: owner/name
    """
    allowed = github_allowed_org()
    if not allowed:
        return None
    if "/" not in repo:
        return {"error": "repo must be 'owner/name' format"}
    owner, _ = repo.split("/", 1)
    if owner.lower() != allowed.lower():
        return github_org_error()
    return None


def scope_code_search_query(query: str, repo: Optional[str]) -> tuple[str, Optional[dict]]:
    """Scope code search to allowed org when GITHUB_DEFAULT_ORG is set."""
    if repo:
        err = enforce_repo_org(repo)
        if err:
            return query, err
        return f"{query} repo:{repo}", None
    allowed = github_allowed_org()
    if allowed:
        return f"{query} org:{allowed}", None
    return query, None


def resolve_list_org(requested_org: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
    """
    Org used for github_list_repos.
    When GITHUB_DEFAULT_ORG is set, always list that org (ignore personal /user/repos).
    """
    allowed = github_allowed_org()
    if allowed:
        if requested_org and requested_org.lower() != allowed.lower():
            return None, {
                "error": f"Only organization '{allowed}' is allowed for this workspace.",
            }
        return allowed, None
    return requested_org, None
