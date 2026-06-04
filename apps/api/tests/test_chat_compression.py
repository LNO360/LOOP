"""Unit tests for compress_and_extract — model call is mocked."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_mock_response(summary: str, memories: list[dict]):
    """Build a minimal OpenAI-style response object."""
    msg = MagicMock()
    msg.content = json.dumps({"summary": summary, "memories": memories})
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


@pytest.mark.asyncio
async def test_compress_returns_summary():
    from core.chat_compression import compress_and_extract

    exchanges = [
        {"user": "Create a task for the pmwani project", "hermes": "Done — created task ID abc-123."},
        {"user": "Make it high priority", "hermes": "Updated task abc-123 to high priority."},
        {"user": "Who is the assignee?", "hermes": "No assignee yet."},
        {"user": "Assign it to Shaan", "hermes": "Assigned task abc-123 to Shaan."},
    ]
    mock_resp = _make_mock_response(
        "• Created task abc-123 in pmwani project\n• Set priority to high\n• Assigned to Shaan",
        [{"key": "task.pmwani.latest_id", "content": "abc-123", "importance": 4}],
    )
    db = AsyncMock()
    with patch("core.chat_compression.chat_with_fallback", return_value=(mock_resp, "test-model")):
        with patch("core.chat_compression.upsert_memories", new_callable=AsyncMock) as mock_upsert:
            summary = await compress_and_extract(exchanges, None, "ws-id-1", db)

    assert "pmwani" in summary
    assert "abc-123" in summary
    mock_upsert.assert_awaited_once()
    saved = mock_upsert.call_args[0][2]  # third positional arg = memories list
    assert saved[0]["key"] == "task.pmwani.latest_id"


@pytest.mark.asyncio
async def test_compress_folds_in_existing_summary():
    from core.chat_compression import compress_and_extract

    exchanges = [{"user": "What's the budget?", "hermes": "Budget is $50k."}]
    mock_resp = _make_mock_response("• Budget is $50k", [])
    db = AsyncMock()
    existing = "• Previously created task abc-123"
    with patch("core.chat_compression.chat_with_fallback", return_value=(mock_resp, "test-model")):
        with patch("core.chat_compression.upsert_memories", new_callable=AsyncMock):
            summary = await compress_and_extract(exchanges, existing, "ws-id-1", db)

    assert summary == "• Budget is $50k"


@pytest.mark.asyncio
async def test_compress_silently_handles_model_failure():
    from core.chat_compression import compress_and_extract

    exchanges = [{"user": "Hello", "hermes": "Hi!"}]
    db = AsyncMock()
    with patch("core.chat_compression.chat_with_fallback", side_effect=Exception("quota exceeded")):
        summary = await compress_and_extract(exchanges, "old summary", "ws-id-1", db)

    assert summary == "old summary"  # returns existing on failure


@pytest.mark.asyncio
async def test_compress_skips_low_importance_memories():
    from core.chat_compression import compress_and_extract

    exchanges = [{"user": "ok thanks", "hermes": "You're welcome!"}]
    mock_resp = _make_mock_response(
        "• Pleasantry exchanged",
        [
            {"key": "something.trivial", "content": "bye", "importance": 1},
            {"key": "something.important", "content": "key fact", "importance": 3},
        ],
    )
    db = AsyncMock()
    with patch("core.chat_compression.chat_with_fallback", return_value=(mock_resp, "test-model")):
        with patch("core.chat_compression.upsert_memories", new_callable=AsyncMock) as mock_upsert:
            await compress_and_extract(exchanges, None, "ws-id-1", db)

    saved = mock_upsert.call_args[0][2]
    assert len(saved) == 1
    assert saved[0]["key"] == "something.important"
