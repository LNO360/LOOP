"""
Shared conversation compression helper.

compress_and_extract() summarises old conversation exchanges into a bullet-point
summary and upserts important facts to workspace memory. Used by both the Hermes
chat session system and the /ai/chat endpoint.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from agents.memory_store import upsert_memories
from core.model_router import chat_with_fallback, get_openrouter_client

logger = logging.getLogger("chat_compression")

_COMPRESS_PROMPT = """\
You are a conversation archiver. Given conversation exchanges (and an optional prior summary),
produce a concise summary and extract important long-term facts.

Return ONLY valid JSON — no markdown, no commentary:
{{
  "summary": "bullet-point summary (3-8 bullets, each starting with •)",
  "memories": [
    {{"key": "dot.notation.key", "content": "one-sentence value", "importance": 1}}
  ]
}}

Rules for summary:
- Preserve task IDs, project names, decisions, outcomes, and any numbers/dates
- Each bullet is one fact or outcome
- Fold the existing_summary into the new summary (don't duplicate facts)

Rules for memories:
- Use dot-notation keys: project.<name>.<field>, task.<title>.id, team.<name>.<field>,
  decision.<topic>, preference.<person>.<topic>
- content is a single sentence or value — not a paragraph
- importance 1-5: 5 = critical ID/decision, 4 = important fact, 3 = useful, 1-2 = skip
- Only emit memories you are confident about; omit trivial or transient facts

existing_summary (fold into new summary):
{existing_summary}

exchanges to compress:
{exchanges_text}
"""


async def compress_and_extract(
    exchanges: list[dict],
    existing_summary: Optional[str],
    workspace_id: str,
    db: AsyncSession,
) -> str:
    """
    Summarise exchanges + existing_summary into a new summary string.
    Upserts memories with importance >= 3 to workspace memory as a side-effect.
    Returns the new summary. On any failure, returns existing_summary unchanged.
    """
    if not exchanges:
        return existing_summary or ""

    exchanges_text = "\n".join(
        f"User: {e['user']}\nHermes: {e['hermes']}" for e in exchanges
    )
    prompt = _COMPRESS_PROMPT.format(
        existing_summary=existing_summary or "(none)",
        exchanges_text=exchanges_text,
    )

    try:
        response, _ = chat_with_fallback(
            profile="agent_chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            client=get_openrouter_client(),
        )
        raw = (response.choices[0].message.content or "").strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
    except Exception as e:
        logger.warning("compress_and_extract: model/parse failed: %s", e)
        return existing_summary or ""

    summary = data.get("summary", existing_summary or "")

    # Re-summarise if summary itself is too long
    if len(summary) > 2000:
        try:
            shrink_resp, _ = chat_with_fallback(
                profile="agent_chat",
                messages=[{
                    "role": "user",
                    "content": (
                        "Condense this summary to under 1500 characters while keeping all key facts:\n\n"
                        + summary
                    ),
                }],
                max_tokens=400,
                client=get_openrouter_client(),
            )
            summary = (shrink_resp.choices[0].message.content or summary).strip()
        except Exception as e:
            logger.warning("compress_and_extract: summary shrink failed: %s", e)

    # Upsert memories — failures are per-item and never block the summary
    raw_memories = [m for m in data.get("memories", []) if isinstance(m, dict)]
    def _imp(m: dict) -> int:
        try:
            return int(m.get("importance", 0))
        except (TypeError, ValueError):
            return 0
    important = [m for m in raw_memories if _imp(m) >= 3]
    if important:
        try:
            await upsert_memories(db, workspace_id, important, source="compression")
        except Exception as e:
            logger.warning("compress_and_extract: memory upsert failed: %s", e)

    return summary
