"""Unit tests for the ACP engine's pure parsing + dispatch logic (no real Hermes process)."""
import asyncio
import json

import pytest

from core.acp_engine import AcpClient, AcpEvent, normalize_update


# ── normalize_update ────────────────────────────────────────────────────────────

def test_text_chunk():
    ev = normalize_update({"sessionUpdate": "agent_message_chunk",
                           "content": {"type": "text", "text": "Hello"}})
    assert ev and ev.type == "text_delta" and ev.text == "Hello"


def test_thought_chunk():
    ev = normalize_update({"sessionUpdate": "agent_thought_chunk",
                           "content": {"type": "text", "text": "hmm"}})
    assert ev and ev.type == "thought" and ev.text == "hmm"


def test_tool_call_start():
    ev = normalize_update({"sessionUpdate": "tool_call", "toolCallId": "t1",
                           "title": "lno_list_tasks", "status": "pending"})
    assert ev and ev.type == "tool_start" and ev.tool_id == "t1"
    assert ev.name == "lno_list_tasks"


def test_tool_call_update_completed():
    ev = normalize_update({"sessionUpdate": "tool_call_update", "toolCallId": "t1",
                           "title": "lno_list_tasks", "status": "completed"})
    assert ev and ev.type == "tool_end" and ev.status == "done" and ev.tool_id == "t1"


def test_tool_call_update_failed():
    ev = normalize_update({"sessionUpdate": "tool_call_update", "toolCallId": "t1",
                           "status": "failed"})
    assert ev and ev.type == "tool_end" and ev.status == "failed"


def test_tool_call_update_in_progress_ignored():
    assert normalize_update({"sessionUpdate": "tool_call_update", "toolCallId": "t1",
                             "status": "in_progress"}) is None


def test_title_update():
    ev = normalize_update({"sessionUpdate": "session_info_update", "title": "Q3 planning"})
    assert ev and ev.type == "title" and ev.title == "Q3 planning"


def test_unsurfaced_updates_return_none():
    for kind in ("available_commands_update", "current_mode_update", "usage_update", "plan"):
        assert normalize_update({"sessionUpdate": kind}) is None


def test_empty_text_chunk_ignored():
    assert normalize_update({"sessionUpdate": "agent_message_chunk",
                             "content": {"type": "text", "text": ""}}) is None


# ── _handle_line dispatch ────────────────────────────────────────────────────────

def test_handle_line_resolves_response():
    loop = asyncio.new_event_loop()
    try:
        c = AcpClient()
        fut = loop.create_future()
        c._pending[7] = fut
        c._handle_line(json.dumps({"jsonrpc": "2.0", "id": 7, "result": {"sessionId": "abc"}}))
        assert fut.done() and fut.result() == {"sessionId": "abc"}
    finally:
        loop.close()


def test_handle_line_response_error():
    loop = asyncio.new_event_loop()
    try:
        c = AcpClient()
        fut = loop.create_future()
        c._pending[8] = fut
        c._handle_line(json.dumps({"jsonrpc": "2.0", "id": 8, "error": {"code": -1, "message": "boom"}}))
        assert fut.done() and fut.exception() is not None
    finally:
        loop.close()


def test_handle_line_pushes_update_to_active_queue():
    c = AcpClient()
    c._active_queue = asyncio.Queue()
    c._handle_line(json.dumps({
        "jsonrpc": "2.0", "method": "session/update",
        "params": {"sessionId": "s", "update": {"sessionUpdate": "agent_message_chunk",
                                                 "content": {"type": "text", "text": "Hi"}}},
    }))
    ev = c._active_queue.get_nowait()
    assert isinstance(ev, AcpEvent) and ev.text == "Hi"


def test_handle_line_permission_request_auto_allows():
    c = AcpClient()
    written: list[dict] = []
    c._write = lambda obj: written.append(obj)  # type: ignore[method-assign]
    c._handle_line(json.dumps({
        "jsonrpc": "2.0", "id": 42, "method": "session/request_permission",
        "params": {"options": [
            {"optionId": "no", "kind": "reject_once"},
            {"optionId": "yes", "kind": "allow_always"},
        ]},
    }))
    assert len(written) == 1
    assert written[0]["id"] == 42
    outcome = written[0]["result"]["outcome"]
    assert outcome["outcome"] == "selected" and outcome["optionId"] == "yes"


def test_handle_line_unknown_request_gets_empty_result():
    c = AcpClient()
    written: list[dict] = []
    c._write = lambda obj: written.append(obj)  # type: ignore[method-assign]
    c._handle_line(json.dumps({"jsonrpc": "2.0", "id": 99, "method": "fs/read_text_file",
                               "params": {}}))
    assert written and written[0]["id"] == 99 and written[0]["result"] == {}


def test_handle_line_ignores_garbage():
    c = AcpClient()
    c._handle_line("not json")
    c._handle_line("")


def test_pick_allow_option_prefers_always():
    assert AcpClient._pick_allow_option([
        {"optionId": "a", "kind": "allow_once"},
        {"optionId": "b", "kind": "allow_always"},
    ]) == "b"


def test_pick_allow_option_none_when_only_reject():
    assert AcpClient._pick_allow_option([{"optionId": "n", "kind": "reject_once"}]) is None
