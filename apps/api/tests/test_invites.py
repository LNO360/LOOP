# apps/api/tests/test_invites.py
import uuid
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"

async def _signup(client, email: str, workspace_name: str = "Test WS"):
    r = await client.post("/api/v1/auth/signup", json={
        "email": email, "password": "pw123",
        "name": "Owner", "workspace_name": workspace_name,
    })
    assert r.status_code == 200
    return r.json()

async def test_create_invite_link(client: AsyncClient):
    data = await _signup(client, _unique_email("owner"))
    token = data["token"]
    ws_id = data["workspace_id"]
    r = await client.post(
        f"/api/v1/workspaces/{ws_id}/invite-link",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "token" in body
    assert "url" in body
    assert len(body["token"]) >= 24

async def test_validate_invite_token(client: AsyncClient):
    data = await _signup(client, _unique_email("owner"))
    token = data["token"]
    ws_id = data["workspace_id"]
    inv = await client.post(
        f"/api/v1/workspaces/{ws_id}/invite-link",
        headers={"Authorization": f"Bearer {token}"},
    )
    inv_token = inv.json()["token"]
    r = await client.get(f"/api/v1/invites/{inv_token}")
    assert r.status_code == 200
    body = r.json()
    assert body["workspace_name"] == "Test WS"
    assert "inviter_name" in body

async def test_accept_invite(client: AsyncClient):
    # Owner creates invite
    owner = await _signup(client, _unique_email("owner"))
    inv = await client.post(
        f"/api/v1/workspaces/{owner['workspace_id']}/invite-link",
        headers={"Authorization": f"Bearer {owner['token']}"},
    )
    inv_token = inv.json()["token"]

    # Member signs up (no workspace_name)
    r2 = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("member"), "password": "pw123", "name": "Member"
    })
    assert r2.status_code == 200
    member_token = r2.json()["token"]

    # Accept invite
    r3 = await client.post(
        f"/api/v1/invites/{inv_token}/accept",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r3.status_code == 200
    assert r3.json()["workspace_id"] == owner["workspace_id"]

async def test_invalid_token_returns_404(client: AsyncClient):
    r = await client.get("/api/v1/invites/nonexistent-token-xyz")
    assert r.status_code == 404
