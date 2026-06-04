"""
MCP tools for web research.

web_search      — Brave Search API (requires Brave API key in workspace integrations)
web_fetch_page  — Fetch and extract clean text from any URL

Core logic lives in core/web_research.py so the boardroom tool layer can reuse it.
"""
from core.web_research import brave_search, fetch_page
from mcp_server.server import mcp


@mcp.tool()
async def web_search(
    workspace_id: str,
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Search the web using Brave Search.
    Requires Brave API key configured in Agent Settings → Integrations.
    Returns list of {title, url, description, published_date}.
    """
    return await brave_search(workspace_id, query, max_results)


@mcp.tool()
async def web_fetch_page(
    url: str,
    max_chars: int = 6000,
) -> dict:
    """
    Fetch a web page and return its clean text content.
    Use after web_search to read the full content of a result.
    max_chars: truncate output to this many characters (default 6000).
    """
    return await fetch_page(url, max_chars)
