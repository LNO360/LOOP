"""
Agent Engine — the single integration point with Hermes via ACP (Agent Client Protocol).

Hermes ships an ACP mode (`hermes acp`): a JSON-RPC 2.0 service over stdio used by
editors. We drive it instead of scraping terminal output, which gives us real token
streaming, structured tool events, session persistence, and the model list for free.

Public surface:
    engine = get_engine()
    client = await engine.get_or_create(conversation_id, hermes_session_id=None)
    # client.session_id is the Hermes ACP sessionId (persist it)
    async for ev in client.prompt(text):
        ...  # AcpEvent: text_delta | thought | tool_start | tool_end | title | usage | done | error

Everything else (1:1 chat, channel @agents) consumes this. Nothing else spawns
Hermes processes or parses its output.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from core.hermes_actions import HERMES_CONTAINER

logger = logging.getLogger("acp_engine")

# Tunables
ACP_INIT_TIMEOUT = 30.0          # seconds to wait for initialize + session setup
ACP_RPC_TIMEOUT = 30.0           # seconds for non-prompt requests
ACP_IDLE_TIMEOUT = 600.0         # close a client idle this long (lazy-reaped)
ACP_CWD = "/root"                # cwd inside the Hermes container


# ── Event contract ────────────────────────────────────────────────────────────

@dataclass
class AcpEvent:
    """Normalized event yielded by AcpClient.prompt()."""
    type: str  # connecting|text_delta|thought|tool_start|tool_end|title|usage|done|error
    text: Optional[str] = None
    name: Optional[str] = None
    tool_id: Optional[str] = None
    status: Optional[str] = None
    detail: Optional[str] = None
    title: Optional[str] = None
    usage: Optional[dict] = None
    stop_reason: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def _text_of(content) -> Optional[str]:
    """Extract text from an ACP content block ({type:'text', text:'…'})."""
    if isinstance(content, dict):
        return content.get("text")
    if isinstance(content, list):
        parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        joined = "".join(parts)
        return joined or None
    return None


def normalize_update(update: dict) -> Optional[AcpEvent]:
    """
    Map one ACP `session/update` payload (the `params.update` object) to an AcpEvent.
    Returns None for updates we don't surface (commands list, mode, plan, usage-only…).

    Pure function — unit-tested directly.
    """
    if not isinstance(update, dict):
        return None
    kind = update.get("sessionUpdate")

    if kind == "agent_message_chunk":
        txt = _text_of(update.get("content"))
        return AcpEvent("text_delta", text=txt) if txt else None

    if kind == "agent_thought_chunk":
        txt = _text_of(update.get("content"))
        return AcpEvent("thought", text=txt) if txt else None

    if kind == "tool_call":
        return AcpEvent(
            "tool_start",
            tool_id=update.get("toolCallId"),
            name=update.get("title") or update.get("kind") or "tool",
            detail=_tool_detail(update),
        )

    if kind == "tool_call_update":
        status = update.get("status")
        # Only surface terminal states as tool_end; ignore in-progress churn.
        if status in ("completed", "failed", "error"):
            return AcpEvent(
                "tool_end",
                tool_id=update.get("toolCallId"),
                name=update.get("title") or "tool",
                status="failed" if status in ("failed", "error") else "done",
                detail=_tool_detail(update),
            )
        return None

    if kind == "session_info_update":
        title = update.get("title")
        return AcpEvent("title", title=title) if title else None

    # available_commands_update, current_mode_update, usage_update, plan → not surfaced
    return None


def _tool_detail(update: dict) -> Optional[str]:
    """Best-effort short detail string for a tool event."""
    content = update.get("content")
    txt = _text_of(content)
    if txt:
        return txt[:500]
    raw = update.get("rawInput")
    if raw is not None:
        try:
            return json.dumps(raw)[:500]
        except Exception:
            return str(raw)[:500]
    return None


# ── JSON-RPC client over one `hermes acp` process ───────────────────────────────

class AcpError(Exception):
    pass


class AcpClient:
    """
    Owns a single `hermes acp` subprocess and one Hermes ACP session.
    JSON-RPC 2.0, newline-delimited, over stdio.
    """

    def __init__(self, container: str = HERMES_CONTAINER, cwd: str = ACP_CWD):
        self._container = container
        self._cwd = cwd
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._next_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._active_queue: Optional[asyncio.Queue] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._closed = False
        self.session_id: Optional[str] = None
        self.models: list[dict] = []
        self.current_model_id: Optional[str] = None
        self.last_used = time.monotonic()
        self._prompt_lock = asyncio.Lock()

    # ── lifecycle ──────────────────────────────────────────────────────────────

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None and not self._closed

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", self._container, "hermes", "acp", "--yes",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        await asyncio.wait_for(
            self._request("initialize", {
                "protocolVersion": 1,
                "clientCapabilities": {"fs": {"readTextFile": False, "writeTextFile": False}},
            }),
            timeout=ACP_INIT_TIMEOUT,
        )

    async def new_session(self, model_id: Optional[str] = None) -> str:
        result = await asyncio.wait_for(
            self._request("session/new", {"cwd": self._cwd, "mcpServers": []}),
            timeout=ACP_INIT_TIMEOUT,
        )
        self._ingest_session_result(result)
        await self._post_session_setup(model_id)
        return self.session_id  # type: ignore[return-value]

    async def load_session(self, session_id: str, model_id: Optional[str] = None) -> str:
        try:
            result = await asyncio.wait_for(
                self._request("session/load", {
                    "sessionId": session_id, "cwd": self._cwd, "mcpServers": [],
                }),
                timeout=ACP_INIT_TIMEOUT,
            )
            self._ingest_session_result(result)
            self.session_id = self.session_id or session_id
        except Exception as e:
            logger.warning("session/load failed (%s); creating fresh session", e)
            await self.new_session(model_id)
            return self.session_id  # type: ignore[return-value]
        await self._post_session_setup(model_id)
        return self.session_id  # type: ignore[return-value]

    def _ingest_session_result(self, result: dict) -> None:
        if not isinstance(result, dict):
            return
        self.session_id = result.get("sessionId") or self.session_id
        models = (result.get("models") or {})
        self.models = models.get("availableModels") or self.models
        self.current_model_id = models.get("currentModelId") or self.current_model_id

    async def _post_session_setup(self, model_id: Optional[str]) -> None:
        # Auto-allow file edits to avoid permission round-trips (trusted server context).
        await self._try("session/set_mode", {"sessionId": self.session_id, "modeId": "dont_ask"})
        if model_id:
            await self.set_model(model_id)

    async def set_model(self, model_id: str) -> None:
        """Best-effort model switch. Hermes may not implement session/set_model on all versions."""
        ok = await self._try("session/set_model", {"sessionId": self.session_id, "modelId": model_id})
        if ok:
            self.current_model_id = model_id

    # ── prompting ────────────────────────────────────────────────────────────────

    async def prompt(self, text: str) -> AsyncIterator[AcpEvent]:
        """Send a prompt; stream normalized events until the turn ends."""
        if not self.alive:
            yield AcpEvent("error", message="Hermes session is not available")
            return
        async with self._prompt_lock:
            self.last_used = time.monotonic()
            queue: asyncio.Queue = asyncio.Queue()
            self._active_queue = queue

            _RESULT = object()
            fut = self._send("session/prompt", {
                "sessionId": self.session_id,
                "prompt": [{"type": "text", "text": text}],
            })

            def _on_done(f: asyncio.Future) -> None:
                queue.put_nowait((_RESULT, f))

            fut.add_done_callback(_on_done)

            yield AcpEvent("connecting")
            try:
                while True:
                    item = await queue.get()
                    if isinstance(item, tuple) and item[0] is _RESULT:
                        f: asyncio.Future = item[1]
                        if f.cancelled():
                            yield AcpEvent("error", message="cancelled")
                        elif f.exception() is not None:
                            yield AcpEvent("error", message=str(f.exception()))
                        else:
                            res = f.result() or {}
                            yield AcpEvent(
                                "done",
                                stop_reason=res.get("stopReason"),
                                usage=res.get("usage"),
                            )
                        return
                    elif isinstance(item, AcpEvent):
                        yield item
            finally:
                self._active_queue = None
                self.last_used = time.monotonic()

    # ── JSON-RPC plumbing ────────────────────────────────────────────────────────

    def _write(self, obj: dict) -> None:
        if not self._proc or not self._proc.stdin:
            raise AcpError("process not started")
        line = (json.dumps(obj) + "\n").encode("utf-8")
        self._proc.stdin.write(line)

    def _send(self, method: str, params: dict) -> asyncio.Future:
        """Send a request, return a future that resolves with its result."""
        self._next_id += 1
        rid = self._next_id
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[rid] = fut
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return fut

    async def _request(self, method: str, params: dict):
        return await self._send(method, params)

    async def _try(self, method: str, params: dict) -> bool:
        """Send a request, swallow errors. Returns True on success."""
        try:
            await asyncio.wait_for(self._request(method, params), timeout=ACP_RPC_TIMEOUT)
            return True
        except Exception as e:
            logger.debug("%s failed/ignored: %s", method, e)
            return False

    def _handle_line(self, line: str) -> None:
        """Dispatch one inbound JSON-RPC line. Pure-ish: only touches state + transport."""
        line = line.strip()
        if not line:
            return
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return

        # Response to one of our requests
        if "id" in msg and ("result" in msg or "error" in msg):
            fut = self._pending.pop(msg["id"], None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(AcpError(str(msg["error"])))
                else:
                    fut.set_result(msg.get("result"))
            return

        method = msg.get("method")
        if not method:
            return

        # Server → client request (needs a response)
        if "id" in msg:
            self._handle_server_request(msg["id"], method, msg.get("params") or {})
            return

        # Notification
        if method == "session/update":
            update = (msg.get("params") or {}).get("update") or {}
            ev = normalize_update(update)
            if ev is not None and self._active_queue is not None:
                self._active_queue.put_nowait(ev)

    def _handle_server_request(self, rid, method: str, params: dict) -> None:
        """Answer requests Hermes makes of us. We auto-allow (trusted server context)."""
        if method == "session/request_permission":
            option_id = self._pick_allow_option(params.get("options") or [])
            outcome = ({"outcome": "selected", "optionId": option_id}
                       if option_id else {"outcome": "cancelled"})
            self._write({"jsonrpc": "2.0", "id": rid, "result": {"outcome": outcome}})
            return
        # Unknown server request → respond with a benign empty result.
        self._write({"jsonrpc": "2.0", "id": rid, "result": {}})

    @staticmethod
    def _pick_allow_option(options: list) -> Optional[str]:
        """Prefer allow_always, then allow_once, then any non-reject option."""
        by_kind = {o.get("kind"): o.get("optionId") for o in options if isinstance(o, dict)}
        for kind in ("allow_always", "allow_once", "allow"):
            if by_kind.get(kind):
                return by_kind[kind]
        for o in options:
            if isinstance(o, dict) and "reject" not in (o.get("kind") or ""):
                return o.get("optionId")
        return None

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        try:
            while True:
                raw = await self._proc.stdout.readline()
                if not raw:
                    break
                self._handle_line(raw.decode("utf-8", errors="replace"))
        except Exception as e:
            logger.warning("ACP read loop error: %s", e)
        finally:
            self._fail_all(AcpError("hermes acp process ended"))

    async def _drain_stderr(self) -> None:
        assert self._proc and self._proc.stderr
        try:
            while True:
                raw = await self._proc.stderr.readline()
                if not raw:
                    break
                logger.debug("acp[stderr] %s", raw.decode("utf-8", errors="replace").rstrip())
        except Exception:
            pass

    def _fail_all(self, exc: Exception) -> None:
        self._closed = True
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()
        if self._active_queue is not None:
            self._active_queue.put_nowait(AcpEvent("error", message=str(exc)))

    async def close(self) -> None:
        self._closed = True
        try:
            if self._proc and self._proc.stdin:
                self._proc.stdin.close()
        except Exception:
            pass
        for t in (self._reader_task, self._stderr_task):
            if t:
                t.cancel()
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()
            except ProcessLookupError:
                pass


# ── Session pool ────────────────────────────────────────────────────────────────

class AcpEngine:
    """Maps conversation-id → live AcpClient. One Hermes session per conversation."""

    def __init__(self):
        self._clients: dict[str, AcpClient] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self,
        key: str,
        hermes_session_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> AcpClient:
        async with self._lock:
            await self._reap_idle_locked()
            client = self._clients.get(key)
            if client and client.alive:
                if model_id and model_id != client.current_model_id:
                    await client.set_model(model_id)
                client.last_used = time.monotonic()
                return client

            client = AcpClient()
            await client.start()
            if hermes_session_id:
                await client.load_session(hermes_session_id, model_id)
            else:
                await client.new_session(model_id)
            self._clients[key] = client
            return client

    async def drop(self, key: str) -> None:
        async with self._lock:
            client = self._clients.pop(key, None)
        if client:
            await client.close()

    async def _reap_idle_locked(self) -> None:
        now = time.monotonic()
        stale = [
            k for k, c in self._clients.items()
            if not c.alive or (c._active_queue is None and now - c.last_used > ACP_IDLE_TIMEOUT)
        ]
        for k in stale:
            c = self._clients.pop(k, None)
            if c:
                await c.close()


_engine: Optional[AcpEngine] = None


def get_engine() -> AcpEngine:
    global _engine
    if _engine is None:
        _engine = AcpEngine()
    return _engine
