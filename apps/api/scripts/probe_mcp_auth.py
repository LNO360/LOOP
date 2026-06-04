#!/usr/bin/env python3
"""
Probe MCP service-token auth without embedding secrets in source.

Usage (from repo root or apps/api):
  python3 apps/api/scripts/probe_mcp_auth.py
  python3 apps/api/scripts/probe_mcp_auth.py --env /opt/lno-os/.env.prod --url http://localhost:8000

Exit codes: 0 = auth OK (not 401), 1 = 401 or missing token, 2 = connection error.

Never paste HERMES_SERVICE_TOKEN into this file. Cursor/chat may show secrets as ***;
that is redaction, not the value in .env.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_token(env_path: Path) -> str:
    if not env_path.is_file():
        print(f"env file not found: {env_path}", file=sys.stderr)
        return ""
    values = dotenv_values(env_path)
    token = (values.get("HERMES_SERVICE_TOKEN") or "").strip()
    if not token:
        print(f"HERMES_SERVICE_TOKEN missing or empty in {env_path}", file=sys.stderr)
    return token


def _token_fingerprint(token: str) -> str:
    if not token:
        return "(empty)"
    return f"len={len(token)} prefix={token[:4]!r} suffix={token[-4:]!r}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe /mcp/mcp Bearer auth")
    parser.add_argument(
        "--env",
        type=Path,
        default=_repo_root() / ".env",
        help="Path to .env or .env.prod (default: repo .env)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/mcp/mcp",
        help="MCP streamable HTTP endpoint (default: http://localhost:8000/mcp/mcp)",
    )
    args = parser.parse_args()

    token = _load_token(args.env)
    print(f"token fingerprint: {_token_fingerprint(token)}")
    if not token:
        return 1

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "probe-mcp-auth", "version": "1.0"},
        },
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            bad = client.post(
                args.url,
                headers={**headers, "Authorization": "Bearer wrong-token"},
                json=init_body,
            )
            resp = client.post(args.url, headers=headers, json=init_body)
            get_resp = client.get(args.url, headers=headers)
    except httpx.HTTPError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 2

    print(f"POST initialize (bad token) -> HTTP {bad.status_code} (want 401)")
    print(f"POST initialize (good token) -> HTTP {resp.status_code}")
    print(f"GET {args.url} -> HTTP {get_resp.status_code} (400/406 normal for bare GET)")

    if bad.status_code != 401:
        print("WARN: bad token did not return 401 — auth middleware may be misconfigured")
    if resp.status_code == 401:
        print("auth FAILED (401) — token mismatch vs api container HERMES_SERVICE_TOKEN")
        return 1
    if resp.status_code in (200, 406):
        print("auth OK — MCP accepted Bearer token")
        if "lno-os" in resp.text or "protocolVersion" in resp.text or "result" in resp.text:
            print("initialize response looks valid")
        return 0
    print(f"initialize body preview: {resp.text[:300]!r}")
    # Non-401 on POST still means token was accepted even if handler errored
    if resp.status_code != 401:
        print("auth OK (not 401) — check body if initialize failed for other reasons")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
