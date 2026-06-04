import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_signup_creates_user_and_workspace(client):
    resp = await client.post("/api/v1/auth/signup", json={
        "email": "test_signup@example.com",
        "password": "password123",
        "name": "Test User",
        "workspace_name": "Test Corp"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert "workspace_id" in data

@pytest.mark.asyncio
async def test_login_returns_token(client):
    await client.post("/api/v1/auth/signup", json={
        "email": "login_test@example.com", "password": "pass123",
        "name": "Login User", "workspace_name": "Login Corp"
    })
    resp = await client.post("/api/v1/auth/login", json={"email": "login_test@example.com", "password": "pass123"})
    assert resp.status_code == 200
    assert "token" in resp.json()

@pytest.mark.asyncio
async def test_me_returns_user(client):
    signup = await client.post("/api/v1/auth/signup", json={
        "email": "me_test@example.com", "password": "pass123",
        "name": "Me User", "workspace_name": "Me Corp"
    })
    token = signup.json()["token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me_test@example.com"
