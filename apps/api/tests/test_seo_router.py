"""
Tests for SEO REST router — overview aggregation with mocked services.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("BETTER_AUTH_SECRET", "test")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import AsyncClient

TEST_EMAIL = "seo_test@example.com"
TEST_PASSWORD = "testpass123"


async def _signup_and_get_ids(client: AsyncClient) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "SEO Tester",
            "workspace_name": "SEO Test WS",
        },
    )
    if r.status_code == 400:
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        return data["token"], data["workspace_id"]

    assert r.status_code in (200, 201), r.text
    data = r.json()
    return data["token"], data["workspace_id"]


@pytest.mark.asyncio
async def test_seo_overview_unauthenticated(client: AsyncClient):
    r = await client.get("/api/v1/workspaces/00000000-0000-0000-0000-000000000001/seo/overview")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_seo_overview_returns_structure(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    mock_overview = {
        "google_connected": False,
        "blog_configured": True,
        "gsc": {"available": False, "reason": "Google not connected"},
        "blog": {
            "available": True,
            "total_posts": 2,
            "draft_count": 1,
            "published_count": 1,
            "avg_score": 75.0,
            "posts_needing_fixes": 1,
        },
    }

    with patch("routers.seo.seo_service.get_overview", new=AsyncMock(return_value=mock_overview)):
        r = await client.get(
            f"/api/v1/workspaces/{ws_id}/seo/overview",
            headers=headers,
        )

    assert r.status_code == 200, r.text
    data = r.json()
    assert "google_connected" in data
    assert "blog" in data
    assert data["blog"]["avg_score"] == 75.0


@pytest.mark.asyncio
async def test_seo_blog_posts_not_configured(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.seo.blog_service.is_configured", return_value=False):
        r = await client.get(
            f"/api/v1/workspaces/{ws_id}/seo/blog/posts",
            headers=headers,
        )

    assert r.status_code == 503


@pytest.mark.asyncio
async def test_seo_blog_posts_with_audit(client: AsyncClient):
    token, ws_id = await _signup_and_get_ids(client)
    headers = {"Authorization": f"Bearer {token}"}

    mock_posts = [
        {
            "id": "post-1",
            "title": "Test",
            "slug": "test",
            "status": "draft",
            "score": 80,
            "issues": [],
            "issue_count": 0,
        }
    ]

    with patch("routers.seo.blog_service.is_configured", return_value=True), \
         patch("routers.seo.blog_service.list_posts_with_audits", new=AsyncMock(return_value=mock_posts)):
        r = await client.get(
            f"/api/v1/workspaces/{ws_id}/seo/blog/posts?include_audit=true",
            headers=headers,
        )

    assert r.status_code == 200, r.text
    assert r.json()["posts"][0]["score"] == 80
