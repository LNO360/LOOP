"""
Tests for mcp_server/tools/lno_blog_tools.py.

Httpx calls are monkeypatched so no real Supabase connection is needed.
"""
import os
import sys
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

# Minimal env to satisfy Settings validation
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("BETTER_AUTH_SECRET", "test")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ["LNO_SITE_SUPABASE_URL"] = "https://test.supabase.co"
os.environ["LNO_SITE_SUPABASE_SERVICE_KEY"] = "test-service-key"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import mcp_server.tools.lno_blog_tools as blog  # noqa: E402 — must be after env setup
from services import blog_service  # noqa: E402
from core import config as cfg_mod  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=False)
def supabase_config(monkeypatch):
    """Ensure settings.lno_site_supabase_url is set for tests that call the HTTP layer.

    conftest.py imports Settings() before our os.environ lines run, so the
    settings singleton may have lno_site_supabase_url="" (from the root .env).
    We patch it per-test via monkeypatch so the guard in each tool passes.
    """
    monkeypatch.setattr(cfg_mod.settings, "lno_site_supabase_url", "https://test.supabase.co")
    monkeypatch.setattr(cfg_mod.settings, "lno_site_supabase_service_key", "test-service-key")


# ── SEO audit unit tests ───────────────────────────────────────────────────────

def test_seo_audit_perfect_post():
    post = {
        "id": "abc",
        "title": "Best Broadband in Kerala 2026",  # 30 chars
        "meta_description": "Compare the best broadband plans in Kerala for 2026 — speed, price, coverage compared.",  # 87 chars
        "excerpt": "A detailed comparison of broadband providers in Kerala.",
        "tags": ["broadband", "kerala"],
        "cover_image_url": "https://cdn.example.com/cover.jpg",
        "slug": "best-broadband-kerala-2026",
        "content": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}]},
    }
    result = blog_service.seo_audit(post)
    assert result["score"] == 100
    assert result["issues"] == []
    assert result["estimated_word_count"] == 2


def test_seo_audit_missing_all():
    result = blog_service.seo_audit({"id": "abc", "title": "", "status": "draft"})
    assert result["score"] < 30
    assert "title missing" in result["issues"]
    assert "meta_description missing" in result["issues"]
    assert "no tags set" in result["issues"]
    assert "cover image missing" in result["issues"]
    assert "slug missing" in result["issues"]


def test_seo_audit_title_too_long():
    post = {
        "id": "abc",
        "title": "A" * 70,
        "meta_description": "A" * 100,
        "excerpt": "x",
        "tags": ["t"],
        "cover_image_url": "http://x",
        "slug": "slug",
    }
    result = blog_service.seo_audit(post)
    assert any("title too long" in i for i in result["issues"])


def test_seo_audit_title_too_short():
    post = {
        "id": "abc",
        "title": "Hi",  # 2 chars — too short
        "meta_description": "A" * 100,
        "excerpt": "x",
        "tags": ["t"],
        "cover_image_url": "http://x",
        "slug": "slug",
    }
    result = blog_service.seo_audit(post)
    assert any("title too short" in i for i in result["issues"])


def test_seo_audit_meta_too_long():
    post = {
        "id": "abc",
        "title": "Short title",
        "meta_description": "x" * 200,
        "excerpt": "x",
        "tags": ["t"],
        "cover_image_url": "http://x",
        "slug": "slug",
    }
    result = blog_service.seo_audit(post)
    assert any("meta_description too long" in i for i in result["issues"])


def test_extract_text_nested():
    node = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "world"},
            ]},
        ],
    }
    text = blog_service.extract_text(node)
    assert "Hello" in text
    assert "world" in text


# ── Tool tests with mocked httpx ──────────────────────────────────────────────

FAKE_WS_ID = "00000000-0000-0000-0000-000000000000"

FAKE_POST = {
    "id": str(uuid.uuid4()),
    "title": "Test Post",
    "slug": "test-post",
    "status": "draft",
    "category": "operator",
    "tags": ["test"],
    "published_at": None,
    "updated_at": "2026-05-31T00:00:00Z",
    "meta_description": "A short test meta description that is long enough to pass.",
    "excerpt": "Short excerpt",
    "cover_image_url": "https://cdn.example.com/img.jpg",
    "content": {"type": "doc", "content": []},
}


def _make_mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _mock_http_client(method: str, return_data):
    """Create a mock httpx.AsyncClient that responds to `method` with `return_data`."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    getattr(mock_client, method).return_value = _make_mock_response(return_data)
    return mock_client


@pytest.mark.asyncio
async def test_lno_blog_list_posts(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [FAKE_POST])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_list_posts("ws-id", status="draft")
    assert isinstance(result, list)
    assert result[0]["title"] == "Test Post"
    call_params = mock_client.get.call_args[1]["params"]
    assert call_params["status"] == "eq.draft"


@pytest.mark.asyncio
async def test_lno_blog_list_posts_all_status(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [FAKE_POST])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    await blog.lno_blog_list_posts("ws-id", status="all")
    call_params = mock_client.get.call_args[1]["params"]
    assert "status" not in call_params


@pytest.mark.asyncio
async def test_lno_blog_get_post_found(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [FAKE_POST])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_get_post("ws-id", FAKE_POST["id"])
    assert result["title"] == "Test Post"


@pytest.mark.asyncio
async def test_lno_blog_get_post_not_found(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_get_post("ws-id", "nonexistent-id")
    assert "error" in result
    assert result["post_id"] == "nonexistent-id"


@pytest.mark.asyncio
async def test_lno_blog_seo_audit(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [FAKE_POST])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_seo_audit("ws-id", FAKE_POST["id"])
    assert "score" in result
    assert "issues" in result
    assert result["has_tags"] is True


@pytest.mark.asyncio
async def test_lno_blog_create_post(monkeypatch, supabase_config):
    content = {"type": "doc", "content": []}
    created = {**FAKE_POST, "id": str(uuid.uuid4()), "title": "New Post"}
    mock_client = _mock_http_client("post", [created])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_create_post("ws-id", "New Post", content)
    assert result["title"] == "New Post"
    body = mock_client.post.call_args[1]["json"]
    assert body["status"] == "draft"
    assert body["title"] == "New Post"


@pytest.mark.asyncio
async def test_lno_blog_update_post(monkeypatch, supabase_config):
    updated = {**FAKE_POST, "meta_description": "Updated description that is long enough."}
    mock_client = _mock_http_client("patch", [updated])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_update_post(
        "ws-id", FAKE_POST["id"], meta_description="Updated description that is long enough."
    )
    assert result["meta_description"] == "Updated description that is long enough."


@pytest.mark.asyncio
async def test_lno_blog_update_post_no_fields(monkeypatch, supabase_config):
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())
    result = await blog.lno_blog_update_post("ws-id", FAKE_POST["id"])
    assert "error" in result


@pytest.mark.asyncio
async def test_lno_blog_publish_post_creates_proposed_action(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [FAKE_POST])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    added = {}
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=None)
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()

    def capture_add(obj):
        added["action"] = obj
        obj.id = uuid.uuid4()

    fake_db.add = capture_add
    monkeypatch.setattr(blog_service, "AsyncSessionLocal", lambda: fake_db)

    result = await blog.lno_blog_publish_post(FAKE_WS_ID, FAKE_POST["id"])
    assert result["proposed"] is True
    assert result["action_type"] == "lno_blog_publish"
    assert added["action"].action_type == "lno_blog_publish"
    assert added["action"].payload["post_id"] == FAKE_POST["id"]


@pytest.mark.asyncio
async def test_lno_blog_delete_post_creates_proposed_action(monkeypatch, supabase_config):
    mock_client = _mock_http_client("get", [FAKE_POST])
    monkeypatch.setattr(blog_service.httpx, "AsyncClient", lambda **kw: mock_client)
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    added = {}
    fake_db = AsyncMock()
    fake_db.__aenter__ = AsyncMock(return_value=fake_db)
    fake_db.__aexit__ = AsyncMock(return_value=None)
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()

    def capture_add(obj):
        added["action"] = obj
        obj.id = uuid.uuid4()

    fake_db.add = capture_add
    monkeypatch.setattr(blog_service, "AsyncSessionLocal", lambda: fake_db)

    result = await blog.lno_blog_delete_post(FAKE_WS_ID, FAKE_POST["id"])
    assert result["proposed"] is True
    assert result["action_type"] == "lno_blog_delete"
    assert added["action"].risk_level == "high"


@pytest.mark.asyncio
async def test_missing_config_returns_error(monkeypatch):
    monkeypatch.setattr(cfg_mod.settings, "lno_site_supabase_url", "")
    monkeypatch.setattr(blog, "agent_broadcast", AsyncMock())

    result = await blog.lno_blog_list_posts("ws-id")
    assert isinstance(result, list)
    assert "error" in result[0]
