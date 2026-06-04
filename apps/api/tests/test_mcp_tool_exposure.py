"""
Tests: MCP tool exposure — verifies the dynamic toolset contract:
  1. lno_find_tools + lno_invoke are registered in the FastMCP server
  2. Domain tools (gmail, github, finance, etc.) are registered in the FastMCP server
  3. Core tools (including proposed_actions) remain in hermes/config.yaml include list
  4. lno_find_tools + lno_invoke are in the include list
  5. Non-core domain tools are NOT in the include list (discoverable via lno_find_tools)

Run from apps/api/:
    uv run pytest tests/test_mcp_tool_exposure.py -v
"""
import sys
import os
import yaml
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
HERMES_CONFIG = os.path.join(REPO_ROOT, "hermes/config.yaml")


def _setup():
    api_dir = os.path.join(REPO_ROOT, "apps/api")
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    os.environ.setdefault("REDIS_URL", "redis://localhost")
    os.environ.setdefault("BETTER_AUTH_SECRET", "test-secret")
    os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
    os.environ.setdefault("S3_ACCESS_KEY", "test")
    os.environ.setdefault("S3_SECRET_KEY", "test")


_setup()

from mcp_server.server import mcp, register_mcp_tools

register_mcp_tools()


def _get_include_list() -> list[str]:
    assert os.path.exists(HERMES_CONFIG), f"Config not found: {HERMES_CONFIG}"
    with open(HERMES_CONFIG) as f:
        cfg = yaml.safe_load(f)
    try:
        return cfg["mcp_servers"]["lno-os"]["tools"]["include"]
    except (KeyError, TypeError):
        pytest.fail("Could not find mcp_servers.lno-os.tools.include in hermes/config.yaml")


# ── Test 1: meta-tools are registered in the MCP server ──────────────────────

def test_mcp_server_registers_meta_tools():
    """lno_find_tools and lno_invoke must be registered after register_mcp_tools()."""
    registered = set(mcp._tool_manager.get_tools().keys())
    for name in ("lno_find_tools", "lno_invoke"):
        assert name in registered, (
            f"'{name}' is NOT registered. Did you add tool_discovery to register_mcp_tools()?"
        )


# ── Test 2: domain tools are registered (so lno_find_tools can discover them) ─

def test_mcp_server_registers_domain_tools():
    """Domain tools must be registered so lno_find_tools can discover them."""
    registered = set(mcp._tool_manager.get_tools().keys())
    required = [
        "gmail_search", "gmail_list_inbox",
        "gdrive_search", "gdrive_read_file",
        "gcal_list_events", "gcal_find_free_slots",
        "github_list_repos", "github_list_issues",
        "finance_get_overview", "finance_list_unpaid_invoices",
        "web_search", "web_fetch_page",
        "lno_list_proposed_actions", "lno_approve_proposed_action", "lno_reject_proposed_action",
    ]
    missing = [t for t in required if t not in registered]
    assert not missing, (
        f"Domain tools not registered (add their modules to register_mcp_tools()):\n"
        + "\n".join(f"  ✗ {t}" for t in missing)
    )


# ── Test 3: core tools are in the include list ────────────────────────────────

def test_hermes_config_has_core_tools():
    """Core lno_* and meta-tools must remain in config.yaml include list."""
    include_list = _get_include_list()
    required = [
        "lno_get_workspace_snapshot",
        "lno_list_tasks", "lno_create_task", "lno_update_task",
        "lno_list_projects", "lno_list_overdue_tasks",
        "lno_get_workspace_memory", "lno_upsert_workspace_memory",
        "lno_search_workspace_memory",
        "lno_send_channel_message", "lno_create_notification",
        "lno_list_proposed_actions", "lno_approve_proposed_action", "lno_reject_proposed_action",
        "lno_read_skill", "lno_list_skills",
        "lno_find_tools", "lno_invoke",
    ]
    missing = [t for t in required if t not in include_list]
    assert not missing, f"Core tools missing from config.yaml include list: {missing}"


# ── Test 4: domain tools are NOT in the include list ─────────────────────────

def test_hermes_config_excludes_domain_tools():
    """
    Domain tools must NOT be in the include list — they are discoverable via
    lno_find_tools, not pre-loaded on every request.
    """
    include_list = _get_include_list()
    should_not_be_present = [
        "gmail_list_inbox", "gmail_search", "gmail_get_email", "gmail_send",
        "gdrive_search", "gdrive_read_file",
        "gcal_list_events", "gcal_find_free_slots",
        "github_list_repos", "github_list_issues", "github_get_issue", "github_list_prs",
        "finance_get_overview", "finance_get_summary", "finance_list_unpaid_invoices",
        "web_search", "web_fetch_page",
        # proposed_actions are core (approval workflow is critical path) — not domain
    ]
    wrongly_included = [t for t in should_not_be_present if t in include_list]
    assert not wrongly_included, (
        f"These domain tools should NOT be in the include list (use lno_find_tools instead):\n"
        + "\n".join(f"  ✗ {t}" for t in wrongly_included)
    )
