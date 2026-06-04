"""Tests for Hermes file read/write endpoints."""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from main import app
import routers.hermes_chat as hermes_module


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


async def _signup_and_auth(client: AsyncClient) -> tuple[str, str]:
    """Sign up a fresh user, return (token, workspace_id)."""
    resp = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("filetest"),
        "password": "pass123",
        "name": "File Tester",
        "workspace_name": "File Corp",
    })
    data = resp.json()
    return data["token"], data["workspace_id"]


@pytest.mark.asyncio
async def test_get_soul_returns_empty_when_missing(client, tmp_path):
    # Redirect to tmp so we don't touch real files
    hermes_module.SOUL_MD_PATH = tmp_path / "SOUL.md"
    token, workspace_id = await _signup_and_auth(client)
    resp = await client.get(
        f"/api/v1/workspaces/{workspace_id}/hermes/soul",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == ""


@pytest.mark.asyncio
async def test_put_then_get_soul(client, tmp_path):
    hermes_module.SOUL_MD_PATH = tmp_path / "SOUL.md"
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    content = "# Test Soul\nYou are a test agent."

    put = await client.put(
        f"/api/v1/workspaces/{workspace_id}/hermes/soul",
        json={"content": content},
        headers=headers,
    )
    assert put.status_code == 200
    assert put.json()["ok"] is True

    get = await client.get(
        f"/api/v1/workspaces/{workspace_id}/hermes/soul",
        headers=headers,
    )
    assert get.json()["content"] == content


@pytest.mark.asyncio
async def test_put_then_get_memory(client, tmp_path):
    hermes_module.MEMORY_MD_PATH = tmp_path / "MEMORY.md"
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    content = "ops.last_scan: 2026-05-26"

    await client.put(
        f"/api/v1/workspaces/{workspace_id}/hermes/memory",
        json={"content": content},
        headers=headers,
    )
    get = await client.get(
        f"/api/v1/workspaces/{workspace_id}/hermes/memory",
        headers=headers,
    )
    assert get.json()["content"] == content


@pytest.mark.asyncio
async def test_put_then_get_user_profile(client, tmp_path):
    hermes_module.USER_MD_PATH = tmp_path / "USER.md"
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    content = "User is a founder who prefers concise summaries."

    await client.put(
        f"/api/v1/workspaces/{workspace_id}/hermes/user-profile",
        json={"content": content},
        headers=headers,
    )
    get = await client.get(
        f"/api/v1/workspaces/{workspace_id}/hermes/user-profile",
        headers=headers,
    )
    assert get.json()["content"] == content


@pytest.mark.asyncio
async def test_put_then_get_config(client, tmp_path):
    hermes_module.CONFIG_YAML_PATH = tmp_path / "config.yaml"
    token, workspace_id = await _signup_and_auth(client)
    headers = {"Authorization": f"Bearer {token}"}
    content = "model:\n  default: test-model\n  provider: openrouter\n"

    await client.put(
        f"/api/v1/workspaces/{workspace_id}/hermes/config",
        json={"content": content},
        headers=headers,
    )
    get = await client.get(
        f"/api/v1/workspaces/{workspace_id}/hermes/config",
        headers=headers,
    )
    assert get.json()["content"] == content


@pytest.mark.asyncio
async def test_unauthenticated_get_returns_401(client):
    resp = await client.get("/api/v1/workspaces/some-id/hermes/soul")
    # FastAPI returns 403 when credentials are missing (HTTPBearer raises 403)
    assert resp.status_code in (401, 403)
