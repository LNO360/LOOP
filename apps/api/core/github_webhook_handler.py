# apps/api/core/github_webhook_handler.py
"""
Background task: build Hermes prompt from a GitHub webhook event and fire docker exec.

process_webhook_event(event_id)  — called by FastAPI BackgroundTasks
build_hermes_prompt(event)       — pure function, returns str | None (None = skip)
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from db.session import AsyncSessionLocal
from models.github_webhook import GithubWebhookEvent, GithubAppInstallation
from models.agent import AgentRun
from core.hermes_actions import docker_exec


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_hermes_prompt(event: GithubWebhookEvent) -> Optional[str]:
    """
    Return a Hermes chat prompt for the event, or None to skip it.
    Pure function — no DB or I/O.
    """
    ws   = str(event.workspace_id)
    repo = event.repo_full_name or "unknown/repo"
    p    = event.payload or {}
    tag  = f"[WORKSPACE:{ws}] [GITHUB_WEBHOOK:{event.event_type}/{event.action or ''}]"

    # ── pull_request ─────────────────────────────────────────────────────────
    if event.event_type == "pull_request":
        pr     = p.get("pull_request", {})
        number = pr.get("number", "?")
        title  = (pr.get("title", "") or "")[:200]   # cap user-controlled input
        author = ((pr.get("user") or {}).get("login") or "unknown")[:80]
        head   = ((pr.get("head") or {}).get("ref") or "?")[:100]
        base   = (pr.get("base") or {}).get("ref", "main")

        if event.action == "opened":
            return (
                f"{tag}\n"
                f"A new pull request was opened in {repo}.\n"
                f"PR #{number}: \"{title}\" by {author}\n"
                f"Base: {base} ← Head: {head}\n\n"
                f"Use github_get_pr to fetch full details and CI status, then:\n"
                f"1. Post a brief summary in the team channel\n"
                f"2. If CI is failing, flag it clearly\n"
                f"3. If the PR has no assignee, suggest one based on changed files"
            )

        if event.action == "closed" and pr.get("merged"):
            return (
                f"{tag}\n"
                f"PR #{number} \"{title}\" was merged into {base} in {repo} by {author}.\n\n"
                f"Use github_get_pr to get the full summary of what changed, then:\n"
                f"1. Post a merge announcement in the team channel\n"
                f"2. List the key changes in 2-3 bullet points"
            )

        if event.action == "review_requested":
            reviewers = [r.get("login") for r in pr.get("requested_reviewers", [])]
            return (
                f"{tag}\n"
                f"PR #{number} \"{title}\" in {repo} has requested review from: "
                f"{', '.join(reviewers) or 'unknown'}.\n\n"
                f"Send a platform DM to each requested reviewer notifying them."
            )

        return None  # synchronize, labeled, etc. — skip

    # ── issues ────────────────────────────────────────────────────────────────
    if event.event_type == "issues":
        issue  = p.get("issue", {})
        number = issue.get("number", "?")
        title  = (issue.get("title", "") or "")[:200]
        author = ((issue.get("user") or {}).get("login") or "unknown")[:80]

        if event.action == "opened":
            return (
                f"{tag}\n"
                f"Issue #{number} \"{title}\" was opened in {repo} by {author}.\n\n"
                f"Use github_get_issue to read the full description, then:\n"
                f"1. Suggest 1-2 appropriate labels based on content\n"
                f"2. If it matches an open platform task, link them\n"
                f"3. Post a triage note in the team channel"
            )

        if event.action == "assigned":
            assignees = [a.get("login") for a in issue.get("assignees", [])]
            return (
                f"{tag}\n"
                f"Issue #{number} \"{title}\" in {repo} was assigned to: "
                f"{', '.join(assignees) or 'unknown'}.\n\n"
                f"Send a platform DM to each assignee notifying them of the assignment."
            )

        if event.action == "closed":
            return (
                f"{tag}\n"
                f"Issue #{number} \"{title}\" was closed in {repo}.\n\n"
                f"Use github_get_issue to get the resolution summary, then post a "
                f"1-sentence closure note in the team channel."
            )

        return None

    # ── push ──────────────────────────────────────────────────────────────────
    if event.event_type == "push":
        ref      = p.get("ref", "")
        repo_obj = p.get("repository", {})
        default  = repo_obj.get("default_branch", "main")

        if ref != f"refs/heads/{default}":
            return None

        commits = p.get("commits", [])
        count   = len(commits)
        msgs    = "\n".join(
            f"  • {c.get('message', '').splitlines()[0][:80]} ({(c.get('author') or {}).get('name', '?')})"
            for c in commits[:5]
        )
        return (
            f"{tag}\n"
            f"{count} commit{'s' if count != 1 else ''} pushed to {default} in {repo}.\n\n"
            f"Commits:\n{msgs}\n\n"
            f"Post a brief push summary in the team channel."
        )

    # ── check_run ─────────────────────────────────────────────────────────────
    if event.event_type == "check_run" and event.action == "completed":
        cr         = p.get("check_run", {})
        conclusion = cr.get("conclusion", "")
        name       = cr.get("name", "CI")
        url        = cr.get("html_url", "")

        if conclusion in ("failure", "timed_out", "action_required"):
            return (
                f"{tag}\n"
                f"CI check \"{name}\" FAILED in {repo}.\n"
                f"Conclusion: {conclusion}\n"
                f"Details: {url}\n\n"
                f"1. Alert the team channel immediately\n"
                f"2. Use github_create_issue to propose a bug task titled "
                f"\"CI failure: {name}\" for human approval"
            )

        return None

    return None


# ── Installation lifecycle sync ────────────────────────────────────────────────

async def sync_installation_mapping(event: GithubWebhookEvent) -> None:
    """
    Keep github_app_installations in sync when GitHub fires lifecycle events:
      installation/created  — update account_login on existing record (workspace
                              must already be mapped via the OAuth callback flow)
      installation/deleted  — mark record inactive by clearing workspace_id
      installation/suspend  — no-op for now
    """
    p             = event.payload or {}
    installation  = p.get("installation", {})
    inst_id       = str(installation.get("id", ""))
    account_login = (installation.get("account") or {}).get("login", "")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GithubAppInstallation).where(
                GithubAppInstallation.installation_id == inst_id
            )
        )
        inst = result.scalar_one_or_none()

        if event.action == "deleted":
            if inst:
                await db.delete(inst)
                await db.commit()
            return

        if inst and account_login:
            # Refresh the login name (org renames, etc.)
            inst.account_login = account_login
            await db.commit()


# ── Background task ────────────────────────────────────────────────────────────

async def process_webhook_event(event_id: uuid.UUID) -> None:
    """
    Background task: build prompt → fire Hermes → update records.
    Called by FastAPI BackgroundTasks after the 200 ACK is sent.
    """
    async with AsyncSessionLocal() as db:
        event = await db.get(GithubWebhookEvent, event_id)
        if not event:
            return

        prompt = build_hermes_prompt(event)
        if prompt is None:
            event.status = "skipped"
            event.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        # Sync installation → workspace mapping on lifecycle events (no Hermes needed)
        if event.event_type == "installation":
            await sync_installation_mapping(event)
            event.status = "skipped"
            event.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        event.status = "processing"
        await db.commit()

        run = AgentRun(
            workspace_id=event.workspace_id,
            trigger_type="github_webhook",
            trigger_payload={
                "event_type": event.event_type,
                "action": event.action,
                "repo": event.repo_full_name,
                "delivery_id": event.delivery_id,
            },
            agent_name="hermes",
            status="running",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        event.agent_run_id = run.id
        await db.commit()

        try:
            proc = await docker_exec(["hermes", "chat", "-q", prompt])
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            exit_code = proc.returncode
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
        except asyncio.TimeoutError:
            exit_code = -1
            output = ""
            run.error = "docker exec timed out after 120s"
        except Exception as exc:
            exit_code = -1
            output = ""
            run.error = str(exc)[:500]

        now = datetime.now(timezone.utc)
        run.status = "done" if exit_code == 0 else "error"
        run.result_summary = output[:2000]
        run.finished_at = now
        event.status = "done" if exit_code == 0 else "error"
        event.processed_at = now
        if exit_code != 0 and not run.error:
            err_msg = output[-500:] or f"exit code {exit_code}"
            run.error = err_msg
            event.error = err_msg
        await db.commit()
