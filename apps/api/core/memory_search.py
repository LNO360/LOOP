"""
Hybrid retrieval over workspace_memories.

Combines two arms:
  • keyword  — case-insensitive ILIKE over key + content, scored by term hits
  • vector   — pgvector cosine distance over the `embedding` column

…merged with Reciprocal Rank Fusion (RRF). The vector arm is skipped gracefully
when embeddings are unavailable (no key / disabled / error), so search ALWAYS
works — it just degrades to keyword-only.

The scoring/merge helpers are pure functions (no DB, no network) so they can be
unit-tested directly.
"""
from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.embeddings import aembed_text
from models.other import WorkspaceMemory

logger = logging.getLogger(__name__)

# Standard RRF damping constant — larger = flatter contribution per rank.
RRF_K = 60

# Cosine-distance threshold below which two memories are "near duplicates".
# distance = 1 - cosine_similarity, so 0.12 ≈ 0.88 similarity.
NEAR_DUPLICATE_DISTANCE = 0.12


# ── Pure helpers (unit-testable) ──────────────────────────────────────────────

def query_terms(query: str) -> list[str]:
    """Lowercased whitespace-split terms; empties removed."""
    return [t for t in re.split(r"\s+", (query or "").strip().lower()) if t]


def keyword_score(key: str, content: str, terms: list[str]) -> float:
    """
    Relevance score for one memory against query terms.
    A hit in the key weighs 2×, a hit in content 1×, plus a coverage bonus for
    matching all terms. Returns 0.0 when nothing matches.
    """
    if not terms:
        return 0.0
    key_l = (key or "").lower()
    content_l = (content or "").lower()
    hits = 0.0
    for t in terms:
        if t in key_l:
            hits += 2.0
        elif t in content_l:
            hits += 1.0
    if hits == 0:
        return 0.0
    coverage = sum(1 for t in terms if t in key_l or t in content_l) / len(terms)
    return hits + coverage


def reciprocal_rank_fusion(
    keyword_ranked: list,
    vector_ranked: list,
    k: int = RRF_K,
) -> dict:
    """
    Merge two ranked ID lists into a combined RRF score per ID:
        score(id) = Σ 1 / (k + rank_in_list + 1)
    Items appearing high in both arms rise to the top.
    """
    scores: dict = {}
    for rank, mid in enumerate(keyword_ranked):
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)
    for rank, mid in enumerate(vector_ranked):
        scores[mid] = scores.get(mid, 0.0) + 1.0 / (k + rank + 1)
    return scores


# ── DB-backed retrieval ───────────────────────────────────────────────────────

async def hybrid_search(
    db: AsyncSession,
    workspace_id,
    query: str,
    limit: int = 10,
    candidate_k: int = 50,
) -> list[dict]:
    """
    Hybrid keyword + vector search. Returns up to `limit` memories as
    [{key, content, importance, source}] ranked by RRF (or keyword-only when no
    embeddings are available).
    """
    ws_id = uuid.UUID(str(workspace_id))
    terms = query_terms(query)
    if not terms:
        return []

    # ── Keyword arm ──
    conditions = []
    for t in terms:
        like = f"%{t}%"
        conditions.append(WorkspaceMemory.key.ilike(like))
        conditions.append(WorkspaceMemory.content.ilike(like))
    kw_rows = (
        await db.execute(
            select(WorkspaceMemory)
            .where(WorkspaceMemory.workspace_id == ws_id, or_(*conditions))
            .limit(candidate_k * 2)
        )
    ).scalars().all()
    kw_scored = sorted(
        ((keyword_score(m.key, m.content, terms), m) for m in kw_rows),
        key=lambda sm: sm[0],
        reverse=True,
    )
    kw_scored = [(s, m) for s, m in kw_scored if s > 0][:candidate_k]
    keyword_ranked = [m.id for _, m in kw_scored]

    # ── Vector arm (best-effort) ──
    vector_rows: list[WorkspaceMemory] = []
    qvec = await aembed_text(query)
    if qvec is not None:
        try:
            vector_rows = (
                await db.execute(
                    select(WorkspaceMemory)
                    .where(
                        WorkspaceMemory.workspace_id == ws_id,
                        WorkspaceMemory.embedding.is_not(None),
                    )
                    .order_by(WorkspaceMemory.embedding.cosine_distance(qvec))
                    .limit(candidate_k)
                )
            ).scalars().all()
        except Exception as e:
            logger.warning(f"[memory_search] vector arm failed: {e}")
    vector_ranked = [m.id for m in vector_rows]

    # ── Merge ──
    by_id = {m.id: m for _, m in kw_scored}
    for m in vector_rows:
        by_id.setdefault(m.id, m)

    if not vector_ranked:
        # Keyword-only fallback; importance breaks ties.
        ranked = sorted(
            kw_scored,
            key=lambda sm: (sm[0], sm[1].importance or 0),
            reverse=True,
        )
        merged_ids = [m.id for _, m in ranked]
    else:
        rrf = reciprocal_rank_fusion(keyword_ranked, vector_ranked)
        merged_ids = sorted(
            rrf,
            key=lambda mid: (rrf[mid], by_id[mid].importance or 0),
            reverse=True,
        )

    return [
        {
            "key": by_id[mid].key,
            "content": by_id[mid].content,
            "importance": by_id[mid].importance,
            "source": by_id[mid].source,
        }
        for mid in merged_ids[: max(1, limit)]
    ]


async def find_near_duplicates(
    db: AsyncSession,
    workspace_id,
    embedding: list[float] | None,
    exclude_key: str | None = None,
    threshold: float = NEAR_DUPLICATE_DISTANCE,
    limit: int = 3,
) -> list[dict]:
    """
    Return existing memories whose embedding is within `threshold` cosine distance
    of `embedding`. Used at write time to surface likely duplicates (Phase 2).
    Returns [] when embeddings are unavailable. Never auto-merges — the caller
    (agent / gardener) decides what to do.
    """
    if embedding is None:
        return []
    ws_id = uuid.UUID(str(workspace_id))
    dist = WorkspaceMemory.embedding.cosine_distance(embedding).label("dist")
    stmt = (
        select(WorkspaceMemory, dist)
        .where(
            WorkspaceMemory.workspace_id == ws_id,
            WorkspaceMemory.embedding.is_not(None),
        )
        .order_by(dist)
        .limit(limit)
    )
    if exclude_key:
        stmt = stmt.where(WorkspaceMemory.key != exclude_key)
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as e:
        logger.warning(f"[memory_search] near-duplicate scan failed: {e}")
        return []
    return [
        {"key": m.key, "content": m.content, "distance": round(float(d), 4)}
        for m, d in rows
        if d is not None and float(d) <= threshold
    ]
