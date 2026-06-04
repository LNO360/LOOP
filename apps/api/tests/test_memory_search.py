"""Tests for hybrid memory search (core/memory_search.py) and the embedding
service (core/embeddings.py).

Pure helpers only — no DB, no network. The DB/vector path is exercised in
integration (requires a pgvector database + embedding provider).
"""
import pytest

from core import memory_search as ms
from core import embeddings as emb


# ── query_terms ───────────────────────────────────────────────────────────────

def test_query_terms_splits_and_lowercases():
    assert ms.query_terms("  Razorpay  Settlements ") == ["razorpay", "settlements"]


def test_query_terms_empty():
    assert ms.query_terms("") == []
    assert ms.query_terms("   ") == []


# ── keyword_score ─────────────────────────────────────────────────────────────

def test_keyword_score_key_hit_weighs_more_than_content_hit():
    terms = ["timezone"]
    key_hit = ms.keyword_score("team.ashik.timezone", "Asia/Kolkata", terms)
    content_hit = ms.keyword_score("team.ashik.tz", "timezone is Asia/Kolkata", terms)
    assert key_hit > content_hit


def test_keyword_score_zero_when_no_match():
    assert ms.keyword_score("team.ashik", "founder", ["razorpay"]) == 0.0


def test_keyword_score_coverage_bonus_for_all_terms():
    terms = ["razorpay", "settlement"]
    both = ms.keyword_score("finance.razorpay", "settlement reconciliation", terms)
    one = ms.keyword_score("finance.razorpay", "monthly invoice", terms)
    assert both > one


def test_keyword_score_no_terms_is_zero():
    assert ms.keyword_score("any.key", "any content", []) == 0.0


# ── reciprocal_rank_fusion ────────────────────────────────────────────────────

def test_rrf_item_in_both_lists_outranks_item_in_one():
    # 'a' is top of keyword AND top of vector; 'b' only in vector; 'c' only keyword
    scores = ms.reciprocal_rank_fusion(["a", "c"], ["a", "b"])
    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    assert ranked[0] == "a"
    assert set(ranked) == {"a", "b", "c"}


def test_rrf_respects_rank_order_within_a_list():
    scores = ms.reciprocal_rank_fusion(["x", "y", "z"], [])
    assert scores["x"] > scores["y"] > scores["z"]


def test_rrf_empty_lists():
    assert ms.reciprocal_rank_fusion([], []) == {}


def test_rrf_k_damping_flattens_scores():
    tight = ms.reciprocal_rank_fusion(["x", "y"], [], k=1)
    flat = ms.reciprocal_rank_fusion(["x", "y"], [], k=1000)
    # Larger k → smaller gap between consecutive ranks.
    assert (tight["x"] - tight["y"]) > (flat["x"] - flat["y"])


# ── embedding service (best-effort) ───────────────────────────────────────────

def test_embed_text_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(emb.settings, "embedding_enabled", False)
    emb._client = None
    assert emb.embed_text("hello") is None


def test_embed_text_returns_none_when_no_key(monkeypatch):
    monkeypatch.setattr(emb.settings, "embedding_enabled", True)
    monkeypatch.setattr(emb.settings, "openrouter_api_key", "")
    emb._client = None
    assert emb.embed_text("hello") is None


def test_embed_text_empty_input_is_none():
    assert emb.embed_text("") is None
    assert emb.embed_text("   ") is None


def test_memory_embedding_input_format():
    assert emb.memory_embedding_input("team.ashik", "founder") == "team.ashik: founder"


@pytest.mark.asyncio
async def test_find_near_duplicates_none_embedding_returns_empty():
    # No embedding → no scan, no DB access.
    out = await ms.find_near_duplicates(db=None, workspace_id="x", embedding=None)
    assert out == []
