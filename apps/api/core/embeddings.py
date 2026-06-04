"""
Embedding service for workspace-memory semantic search.

Uses OpenRouter's OpenAI-compatible /embeddings endpoint (reuses OPENROUTER_API_KEY),
so no new provider, key, or service is required — embeddings are just another
OpenRouter API call alongside chat.

Embeddings are BEST-EFFORT. If embeddings are disabled, no key is set, or the
provider errors, callers receive None and the system falls back to keyword search.
Memory writes must NEVER fail because an embedding could not be produced.
"""
from __future__ import annotations

import asyncio
import logging

from openai import OpenAI

from core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    if not settings.embedding_enabled or not settings.openrouter_api_key:
        return None
    if _client is None:
        _client = OpenAI(
            base_url=OPENROUTER_BASE,
            api_key=settings.openrouter_api_key,
            default_headers={
                "HTTP-Referer": "https://lno-os.app",
                "X-Title": "LNO OS",
            },
        )
    return _client


def embed_text(text: str) -> list[float] | None:
    """
    Return an embedding vector for `text`, or None if embeddings are unavailable.
    Synchronous — for async callers use `aembed_text`.
    """
    text = (text or "").strip()
    if not text:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.embeddings.create(
            model=settings.embedding_model,
            input=text[:8000],  # cap input; memory entries are short anyway
        )
        vec = resp.data[0].embedding
        if vec and len(vec) == settings.embedding_dim:
            return list(vec)
        logger.warning(
            f"[embeddings] unexpected dim {len(vec) if vec else 0} "
            f"(expected {settings.embedding_dim}) from {settings.embedding_model}"
        )
        return None
    except Exception as e:
        logger.warning(f"[embeddings] embed failed ({settings.embedding_model}): {e}")
        return None


async def aembed_text(text: str) -> list[float] | None:
    """Async wrapper — runs the sync embedding call off the event loop."""
    return await asyncio.to_thread(embed_text, text)


def memory_embedding_input(key: str, content: str) -> str:
    """Canonical text we embed for a memory row: namespaced key + content."""
    return f"{key}: {content}".strip()
