"""Unit tests for the boardroom tool layer (core/boardroom_tools.py)."""
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

from core import boardroom_tools as bt  # noqa: E402


def test_catalog_and_tool_names_consistent():
    names = {t["name"] for t in bt.CATALOG}
    assert names == bt.tool_names()
    # Every catalog entry has a category + schema in the registry.
    for t in bt.CATALOG:
        assert t["category"] in {"research", "workspace_read", "workspace_write", "calc"}


def test_tool_schemas_skips_unknown_names():
    schemas = bt.tool_schemas(["web_search", "nonexistent", "calculate"])
    names = [s["function"]["name"] for s in schemas]
    assert names == ["web_search", "calculate"]


@pytest.mark.asyncio
async def test_calculate_basic():
    out = await bt.execute_tool("calculate", "ws", {"expression": "(1200 * 12) / 2"})
    assert out["result"] == 7200


@pytest.mark.asyncio
async def test_calculate_rejects_non_arithmetic():
    out = await bt.execute_tool("calculate", "ws", {"expression": "__import__('os').system('ls')"})
    assert "error" in out


@pytest.mark.asyncio
async def test_calculate_division_by_zero():
    out = await bt.execute_tool("calculate", "ws", {"expression": "1/0"})
    assert out["error"] == "division by zero"


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    out = await bt.execute_tool("does_not_exist", "ws", {})
    assert "unknown tool" in out["error"]


@pytest.mark.asyncio
async def test_web_search_handler_wraps_results(monkeypatch):
    async def fake_search(workspace_id, query, max_results):
        return [{"title": "Hit", "url": "https://e.com", "description": "d", "published_date": ""}]

    monkeypatch.setattr(bt, "brave_search", fake_search)
    out = await bt.execute_tool("web_search", "ws", {"query": "test"})
    assert out["results"][0]["url"] == "https://e.com"


@pytest.mark.asyncio
async def test_bad_arguments_returns_error():
    # web_search requires `query`; omit it
    out = await bt.execute_tool("web_search", "ws", {"max_results": 3})
    assert "error" in out
