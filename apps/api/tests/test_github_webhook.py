# apps/api/tests/test_github_webhook.py
"""Tests for POST /api/v1/webhooks/github"""
import hashlib
import hmac
import json
import pytest


def _sign(body: bytes, secret: str = "test-secret") -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


PR_OPENED_PAYLOAD = {
    "action": "opened",
    "installation": {"id": 99999},
    "pull_request": {
        "number": 42,
        "title": "feat: billing",
        "user": {"login": "octocat"},
        "head": {"ref": "feat/billing", "sha": "abc123"},
        "base": {"ref": "main"},
    },
    "repository": {"full_name": "LNO360/lno-os", "default_branch": "main"},
}


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(client):
    body = json.dumps(PR_OPENED_PAYLOAD).encode()
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-001",
            "X-Hub-Signature-256": "sha256=badhash",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_missing_signature_rejected(client):
    body = json.dumps(PR_OPENED_PAYLOAD).encode()
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-002",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(client, monkeypatch):
    # Patch webhook secret so the endpoint matches our test secret
    monkeypatch.setattr("routers.github_webhook.WEBHOOK_SECRET", "test-secret")
    # Patch background task to be a no-op
    monkeypatch.setattr(
        "routers.github_webhook.process_webhook_event",
        lambda event_id: None,
    )
    body = json.dumps(PR_OPENED_PAYLOAD).encode()
    resp = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "delivery-unique-001",
            "X-Hub-Signature-256": _sign(body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


@pytest.mark.asyncio
async def test_webhook_deduplicates_same_delivery(client, monkeypatch):
    monkeypatch.setattr("routers.github_webhook.WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(
        "routers.github_webhook.process_webhook_event",
        lambda event_id: None,
    )
    body = json.dumps(PR_OPENED_PAYLOAD).encode()
    headers = {
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "delivery-dup-001",
        "X-Hub-Signature-256": _sign(body),
        "Content-Type": "application/json",
    }
    # First delivery — should be 200
    r1 = await client.post("/api/v1/webhooks/github", content=body, headers=headers)
    assert r1.status_code == 200
    # Exact same delivery_id — should also return 200 (idempotent, no duplicate row)
    r2 = await client.post("/api/v1/webhooks/github", content=body, headers=headers)
    assert r2.status_code == 200


# ── Prompt builder tests ──────────────────────────────────────────────────────
import uuid as _uuid  # avoid collision with any existing uuid import

from core.github_webhook_handler import build_hermes_prompt
from models.github_webhook import GithubWebhookEvent as _GWE


def _make_event(**kwargs) -> _GWE:
    defaults = dict(
        id=_uuid.uuid4(),
        workspace_id=_uuid.uuid4(),
        installation_id="99999",
        delivery_id="test",
        event_type="pull_request",
        action="opened",
        repo_full_name="LNO360/lno-os",
        payload={
            "pull_request": {
                "number": 42,
                "title": "feat: billing",
                "user": {"login": "octocat"},
                "head": {"ref": "feat/billing"},
                "base": {"ref": "main"},
                "merged": False,
            },
            "repository": {"default_branch": "main"},
        },
        status="received",
    )
    defaults.update(kwargs)
    evt = _GWE()
    for k, v in defaults.items():
        setattr(evt, k, v)
    return evt


def test_prompt_pr_opened():
    evt = _make_event(event_type="pull_request", action="opened")
    prompt = build_hermes_prompt(evt)
    assert prompt is not None
    assert "PR #42" in prompt
    assert "feat/billing" in prompt
    assert "github_get_pr" in prompt


def test_prompt_pr_closed_merged():
    evt = _make_event(
        event_type="pull_request",
        action="closed",
        payload={
            "pull_request": {
                "number": 10,
                "title": "fix: bug",
                "user": {"login": "dev"},
                "head": {"ref": "fix/bug"},
                "base": {"ref": "main"},
                "merged": True,
            },
            "repository": {"default_branch": "main"},
        },
    )
    prompt = build_hermes_prompt(evt)
    assert prompt is not None
    assert "merged" in prompt.lower()


def test_prompt_pr_synchronize_is_skipped():
    evt = _make_event(event_type="pull_request", action="synchronize")
    assert build_hermes_prompt(evt) is None


def test_prompt_issue_opened():
    evt = _make_event(
        event_type="issues",
        action="opened",
        payload={
            "issue": {"number": 5, "title": "crash on login", "user": {"login": "reporter"}},
            "repository": {"full_name": "LNO360/lno-os"},
        },
    )
    prompt = build_hermes_prompt(evt)
    assert prompt is not None
    assert "Issue #5" in prompt
    assert "github_get_issue" in prompt


def test_prompt_push_default_branch():
    evt = _make_event(
        event_type="push",
        action=None,
        payload={
            "ref": "refs/heads/main",
            "commits": [{"id": "abc", "message": "fix: typo", "author": {"name": "dev"}}],
            "repository": {"default_branch": "main", "full_name": "LNO360/lno-os"},
        },
    )
    prompt = build_hermes_prompt(evt)
    assert prompt is not None
    assert "1 commit" in prompt


def test_prompt_push_non_default_is_skipped():
    evt = _make_event(
        event_type="push",
        action=None,
        payload={
            "ref": "refs/heads/feat/wip",
            "commits": [],
            "repository": {"default_branch": "main", "full_name": "LNO360/lno-os"},
        },
    )
    assert build_hermes_prompt(evt) is None


def test_prompt_check_run_failure():
    evt = _make_event(
        event_type="check_run",
        action="completed",
        payload={
            "check_run": {
                "name": "CI",
                "conclusion": "failure",
                "html_url": "https://github.com/check/1",
            },
            "repository": {"full_name": "LNO360/lno-os"},
        },
    )
    prompt = build_hermes_prompt(evt)
    assert prompt is not None
    assert "CI" in prompt
    assert "fail" in prompt.lower()


def test_prompt_check_run_success_is_skipped():
    evt = _make_event(
        event_type="check_run",
        action="completed",
        payload={
            "check_run": {"name": "CI", "conclusion": "success", "html_url": "https://github.com/check/1"},
            "repository": {"full_name": "LNO360/lno-os"},
        },
    )
    assert build_hermes_prompt(evt) is None


def test_prompt_unknown_event_is_skipped():
    evt = _make_event(event_type="star", action="created")
    assert build_hermes_prompt(evt) is None
