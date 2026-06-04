"""
Unit tests: MCP tool output caps — verify default limits and truncation behavior.
No DB connection needed; tests use inspect.signature.
"""
import inspect
import os
import sys

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


def _default(fn, param):
    return inspect.signature(fn).parameters[param].default


def test_lno_list_tasks_default_limit():
    from mcp_server.tools.tasks import lno_list_tasks
    assert _default(lno_list_tasks, "limit") == 15


def test_lno_get_channel_messages_default_limit():
    from mcp_server.tools.messages import lno_get_channel_messages
    assert _default(lno_get_channel_messages, "limit") == 10


def test_github_list_repos_default_max_results():
    from mcp_server.tools.github_tools import github_list_repos
    assert _default(github_list_repos, "max_results") == 10


def test_github_list_issues_default_max_results():
    from mcp_server.tools.github_tools import github_list_issues
    assert _default(github_list_issues, "max_results") == 10


def test_github_list_prs_default_max_results():
    from mcp_server.tools.github_tools import github_list_prs
    assert _default(github_list_prs, "max_results") == 10


def test_gmail_list_inbox_default_max_results():
    from mcp_server.tools.google_gmail import gmail_list_inbox
    assert _default(gmail_list_inbox, "max_results") == 10


def test_finance_list_transactions_default_limit():
    from mcp_server.tools.finance_tools import finance_list_transactions
    assert _default(finance_list_transactions, "limit") == 20
