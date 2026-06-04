"""
Tests for lno_find_tools and lno_invoke (tool_discovery.py).

Run from apps/api/:
    uv run pytest tests/test_tool_discovery.py -v
"""
import os
import sys
import asyncio
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))


def _setup_env():
    api_dir = os.path.join(REPO_ROOT, "apps/api")
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    os.environ.setdefault("REDIS_URL", "redis://localhost")
    os.environ.setdefault("BETTER_AUTH_SECRET", "test-secret")
    os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
    os.environ.setdefault("S3_ACCESS_KEY", "test")
    os.environ.setdefault("S3_SECRET_KEY", "test")


_setup_env()

from mcp_server.server import mcp, register_mcp_tools

register_mcp_tools()

from mcp_server.tools.tool_discovery import lno_find_tools, lno_invoke, CORE_TOOLS


# ── lno_find_tools ─────────────────────────────────────────────────────────────

def test_find_tools_returns_gmail_for_email_intent():
    results = asyncio.run(lno_find_tools("search email inbox"))
    names = [r["name"] for r in results]
    assert any("gmail" in n for n in names), f"Expected a gmail tool, got: {names}"


def test_find_tools_category_filter_gmail():
    results = asyncio.run(lno_find_tools("anything", category="gmail"))
    assert results, "Expected at least one gmail tool"
    assert all("gmail" in r["name"] for r in results), (
        f"Non-gmail tools returned for category='gmail': {[r['name'] for r in results]}"
    )


def test_find_tools_category_filter_calendar():
    results = asyncio.run(lno_find_tools("anything", category="calendar"))
    assert results, "Expected at least one calendar tool"
    assert all("gcal" in r["name"] for r in results), (
        f"Non-calendar tools returned: {[r['name'] for r in results]}"
    )


def test_find_tools_excludes_core_tools():
    # Even if intent keywords match core tool names, they must not appear
    results = asyncio.run(lno_find_tools("list tasks workspace snapshot memory"))
    names = {r["name"] for r in results}
    overlap = names & CORE_TOOLS
    assert not overlap, f"Core tools leaked into find_tools results: {overlap}"


def test_find_tools_excludes_meta_tools():
    results = asyncio.run(lno_find_tools("find tools invoke dispatch"))
    names = {r["name"] for r in results}
    assert "lno_find_tools" not in names
    assert "lno_invoke" not in names


def test_find_tools_result_has_compact_format():
    results = asyncio.run(lno_find_tools("search email gmail"))
    assert results, "Expected at least one result"
    tool = results[0]
    assert "name" in tool
    assert "description" in tool
    assert "usage" in tool
    assert "parameters" not in tool, "Full schema must not appear in compact output"
    assert "(" in tool["usage"] and ")" in tool["usage"], (
        f"usage should be a function signature, got: {tool['usage']}"
    )


def test_find_tools_returns_at_most_4_on_keyword_match():
    results = asyncio.run(lno_find_tools("gmail email search"))
    assert len(results) <= 4, f"Expected ≤4 results, got {len(results)}"


def test_find_tools_returns_full_catalogue_on_no_match():
    results = asyncio.run(lno_find_tools("zzzzz_no_match_xyz"))
    # Falls back to alphabetical catalogue — more than 4 but capped at 12
    assert len(results) > 4, (
        f"Expected catalogue (>4) on zero-score intent, got {len(results)}"
    )
    assert len(results) <= 12, (
        f"Expected cap of 12 on fallback, got {len(results)}"
    )


# ── lno_invoke ─────────────────────────────────────────────────────────────────

def test_invoke_unknown_tool_returns_error_dict():
    result = asyncio.run(lno_invoke("nonexistent_tool_xyz_abc", {}))
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "error" in result
    assert "nonexistent_tool_xyz_abc" in result["error"]
    assert "lno_find_tools" in result["error"]


def test_invoke_dispatches_to_registered_tool():
    @mcp.tool(name="_test_echo_dispatch")
    async def _test_echo_dispatch(message: str) -> dict:
        return {"echo": message}

    try:
        result = asyncio.run(lno_invoke("_test_echo_dispatch", {"message": "ping"}))
        # tool.run() returns list[TextContent]; verify it's non-empty and contains "ping"
        assert result, f"Expected non-empty result, got: {result}"
        result_text = str(result)
        assert "ping" in result_text, f"Expected 'ping' in result: {result_text}"
    finally:
        mcp._tool_manager.remove_tool("_test_echo_dispatch")


def test_invoke_invalid_args_returns_error_dict():
    @mcp.tool(name="_test_required_arg")
    async def _test_required_arg(required_arg: str) -> dict:
        return {"val": required_arg}

    try:
        result = asyncio.run(lno_invoke("_test_required_arg", {}))
        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid args" in result["error"] or "_test_required_arg" in result["error"]
    finally:
        mcp._tool_manager.remove_tool("_test_required_arg")


# ── Finance and GitHub discovery (requires Task 3 registration) ───────────────

def test_find_tools_category_filter_finance():
    results = asyncio.run(lno_find_tools("anything", category="finance"))
    assert results, "Expected at least one finance tool — is finance_tools registered?"
    assert all("finance" in r["name"] for r in results), (
        f"Non-finance tools returned: {[r['name'] for r in results]}"
    )


def test_find_tools_returns_finance_for_invoice_intent():
    results = asyncio.run(lno_find_tools("unpaid invoices finance overview"))
    names = [r["name"] for r in results]
    assert any("finance" in n for n in names), (
        f"Expected a finance tool for invoice intent, got: {names}"
    )


def test_find_tools_category_filter_github():
    results = asyncio.run(lno_find_tools("anything", category="github"))
    assert results, "Expected at least one github tool — is github_tools registered?"
    assert all("github" in r["name"] for r in results), (
        f"Non-github tools returned: {[r['name'] for r in results]}"
    )
