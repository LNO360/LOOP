"""
Shared web-research helpers.

Plain async functions used by both the MCP web tools (mcp_server/tools/web_search.py)
and the boardroom tool layer (core/boardroom_tools.py). Keeping the logic here means
there is a single source of truth for Brave search + page extraction.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

import httpx

from core.config import settings
from core.integrations import get_integration, decrypt
from db.session import AsyncSessionLocal


class _TextExtractor(HTMLParser):
    """Minimal HTML → plain text extractor."""

    SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self.SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def get_text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


async def brave_search(
    workspace_id: str,
    query: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Search the web using Brave Search.

    Prefers the workspace integration key, falls back to the server-level key.
    Returns a list of {title, url, description, published_date}, or a single
    {"error": ...} dict if the key is missing or the API fails.
    """
    async with AsyncSessionLocal() as db:
        integration = await get_integration(db, workspace_id, "brave")

    if integration and integration.api_key:
        brave_key = decrypt(integration.api_key)
    else:
        brave_key = settings.brave_search_api_key
        if not brave_key:
            return [{
                "error": (
                    "Brave Search not configured. "
                    "Add your Brave API key at AI Work → Settings → Integrations."
                )
            }]

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(max_results, 20)},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": brave_key,
            },
            timeout=15,
        )

    if resp.status_code != 200:
        return [{"error": f"Brave Search API error: {resp.status_code} {resp.text[:200]}"}]

    data = resp.json()
    results = data.get("web", {}).get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "description": r.get("description", ""),
            "published_date": r.get("page_age", ""),
        }
        for r in results
    ]


async def fetch_page(url: str, max_chars: int = 6000) -> dict:
    """
    Fetch a web page and return its clean text content.

    Returns {url, title, content, truncated, total_chars} or {"error": ...}.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; LNO-OS-Research-Bot/1.0)"
                },
                timeout=10,
            )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return {"error": f"Timeout fetching {url}"}
    except Exception as e:
        return {"error": f"Could not fetch {url}: {str(e)[:200]}"}

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        extractor = _TextExtractor()
        extractor.feed(resp.text)
        text = extractor.get_text()
    else:
        text = resp.text

    truncated = len(text) > max_chars
    return {
        "url": str(resp.url),
        "title": "",
        "content": text[:max_chars],
        "truncated": truncated,
        "total_chars": len(text),
    }
