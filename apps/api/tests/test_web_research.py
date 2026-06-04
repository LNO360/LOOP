"""Tests for MCP web search stack (SearXNG + fetch)."""
import os
import sys

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
API_DIR = os.path.join(REPO_ROOT, "apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("BETTER_AUTH_SECRET", "test-secret")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")


@pytest.mark.asyncio
async def test_run_web_search_searxng(monkeypatch):
    from mcp_server.tools import web_search as ws

    class FakeResp:
        status_code = 200

        def json(self):
            return {
                "results": [
                    {
                        "title": "Example",
                        "url": "https://example.com",
                        "content": "snippet",
                    }
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return FakeResp()

    monkeypatch.setattr(ws.settings, "searxng_url", "http://searxng:8080")
    monkeypatch.setattr(ws.httpx, "AsyncClient", lambda: FakeClient())

    out = await ws.run_web_search("test query", max_results=3)
    assert out["backend"] == "searxng"
    assert len(out["results"]) == 1
    assert out["results"][0]["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_run_web_search_falls_back_to_ddg(monkeypatch):
    from mcp_server.tools import web_search as ws

    async def fail_searx(*_a, **_k):
        raise ConnectionError("searx down")

    async def fake_ddg(query, max_results):
        return [
            {
                "title": "DDG Hit",
                "url": "https://ddg.example",
                "description": "body",
                "published_date": "",
                "source": "duckduckgo",
            }
        ]

    monkeypatch.setattr(ws, "_search_searxng", fail_searx)
    monkeypatch.setattr(ws, "_search_duckduckgo", fake_ddg)

    out = await ws.run_web_search("fallback test", max_results=2)
    assert out["backend"] == "duckduckgo"
    assert out["results"][0]["url"] == "https://ddg.example"
