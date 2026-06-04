"""Tests for _maybe_compress_history in ai_routes."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_compress_response(summary: str):
    msg = MagicMock()
    msg.content = json.dumps({"summary": summary, "memories": []})
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_maybe_compress_noop_below_threshold():
    from routers.ai_routes import _maybe_compress_history

    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}] * 5
    db = AsyncMock()
    result, compressed = await _maybe_compress_history(history, "ws-1", db)
    assert result == history
    assert compressed is False


@pytest.mark.asyncio
async def test_maybe_compress_fires_above_threshold():
    from routers.ai_routes import _maybe_compress_history

    # 32 messages = 16 turns (above threshold of 30)
    history = [{"role": "user", "content": f"msg{i}"} for i in range(32)]
    db = AsyncMock()

    with patch("routers.ai_routes.compress_and_extract", new_callable=AsyncMock, return_value="• Summary"):
        result, compressed = await _maybe_compress_history(history, "ws-1", db)

    assert compressed is True
    assert len(result) < len(history)
    # First item should be the summary block
    assert result[0]["role"] == "system"
    assert "[CONVERSATION SUMMARY]" in result[0]["content"]
    # Last 10 messages kept verbatim
    assert result[-1] == history[-1]
    assert len([m for m in result if m["role"] != "system"]) == 10


@pytest.mark.asyncio
async def test_maybe_compress_returns_original_on_failure():
    from routers.ai_routes import _maybe_compress_history

    history = [{"role": "user", "content": f"msg{i}"} for i in range(32)]
    db = AsyncMock()

    with patch("routers.ai_routes.compress_and_extract", new_callable=AsyncMock, side_effect=Exception("fail")):
        result, compressed = await _maybe_compress_history(history, "ws-1", db)

    assert result == history
    assert compressed is False
