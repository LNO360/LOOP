"""
Integration tests for LNO OS Phase 1 full flow.
Tests: auth → workspace → channel → message → task creation from message.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _unique_email(prefix: str) -> str:
    """Generate a unique email to avoid conflicts between test runs."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.mark.asyncio
async def test_health_check(client):
    """API should return 200 on health endpoint."""
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_signup_creates_workspace(client):
    """POST /api/v1/auth/signup should create user + workspace, return token + workspace_id."""
    r = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("qa"),
        "password": "Test1234!",
        "name": "QA User",
        "workspace_name": "QA Workspace"
    })
    assert r.status_code in (200, 201)
    data = r.json()
    assert "token" in data
    assert "workspace_id" in data
    assert "user_id" in data


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected(client):
    """Second signup with same email should return 400."""
    email = _unique_email("dupe")
    payload = {
        "email": email,
        "password": "Test1234!",
        "name": "Dup User",
        "workspace_name": "Dup WS"
    }
    r1 = await client.post("/api/v1/auth/signup", json=payload)
    assert r1.status_code in (200, 201)
    r2 = await client.post("/api/v1/auth/signup", json=payload)
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_login_returns_token(client):
    """POST /api/v1/auth/login should return token for valid credentials."""
    email = _unique_email("login")
    await client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": "Test1234!",
        "name": "Login Test",
        "workspace_name": "Login WS"
    })
    r = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Test1234!"
    })
    assert r.status_code == 200
    assert "token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client):
    """POST /api/v1/auth/login with wrong password should return 401."""
    email = _unique_email("wrongpw")
    await client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": "Test1234!",
        "name": "WrongPW User",
        "workspace_name": "WrongPW WS"
    })
    r = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "WrongPassword!"
    })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client):
    """GET /api/v1/auth/me should return user data for authenticated user."""
    email = _unique_email("me")
    signup = await client.post("/api/v1/auth/signup", json={
        "email": email,
        "password": "Test1234!",
        "name": "Me User",
        "workspace_name": "Me WS"
    })
    token = signup.json()["token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


@pytest.mark.asyncio
async def test_me_unauthenticated_rejected(client):
    """GET /api/v1/auth/me without token should return 401 or 403."""
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_channel(client):
    """Should be able to create a channel in a workspace."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("channel"),
        "password": "Test1234!",
        "name": "Channel Test",
        "workspace_name": "Channel WS"
    })
    d = signup.json()
    token = d["token"]
    workspace_id = d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels",
        json={"name": "general", "type": "public"},
        headers=headers
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["name"] == "general"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_channels(client):
    """Should list channels in a workspace."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("listch"),
        "password": "Test1234!",
        "name": "ListCh Test",
        "workspace_name": "ListCh WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels",
        json={"name": "announcements", "type": "public"},
        headers=headers
    )
    r = await client.get(f"/api/v1/workspaces/{workspace_id}/channels", headers=headers)
    assert r.status_code == 200
    names = [ch["name"] for ch in r.json()]
    assert "announcements" in names


@pytest.mark.asyncio
async def test_send_and_list_messages(client):
    """Should be able to send and retrieve messages in a channel."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("msg"),
        "password": "Test1234!",
        "name": "Msg Test",
        "workspace_name": "Msg WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    ch = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels",
        json={"name": "test-channel", "type": "public"},
        headers=headers
    )
    channel_id = ch.json()["id"]

    send = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels/{channel_id}/messages",
        json={"content": "Hello, world!"},
        headers=headers
    )
    assert send.status_code in (200, 201)
    assert send.json()["content"] == "Hello, world!"

    msgs = await client.get(
        f"/api/v1/workspaces/{workspace_id}/channels/{channel_id}/messages",
        headers=headers
    )
    assert msgs.status_code == 200
    messages = msgs.json()
    assert any(m["content"] == "Hello, world!" for m in messages)


@pytest.mark.asyncio
async def test_delete_message(client):
    """Message author should be able to delete their message."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("delmsg"),
        "password": "Test1234!",
        "name": "DelMsg Test",
        "workspace_name": "DelMsg WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    ch = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels",
        json={"name": "delete-test", "type": "public"},
        headers=headers
    )
    channel_id = ch.json()["id"]

    send = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels/{channel_id}/messages",
        json={"content": "To be deleted"},
        headers=headers
    )
    msg_id = send.json()["id"]

    del_r = await client.delete(f"/api/v1/messages/{msg_id}", headers=headers)
    assert del_r.status_code == 200
    assert del_r.json()["deleted"] is True


@pytest.mark.asyncio
async def test_create_task(client):
    """Should be able to create a task in a workspace."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("task"),
        "password": "Test1234!",
        "name": "Task Test",
        "workspace_name": "Task WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{workspace_id}/tasks",
        json={"title": "Fix the login bug", "priority": "high"},
        headers=headers
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["title"] == "Fix the login bug"
    assert data["priority"] == "high"
    assert data["status"] == "todo"


@pytest.mark.asyncio
async def test_update_task_status(client):
    """Task status should be updatable via PATCH."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("taskup"),
        "password": "Test1234!",
        "name": "TaskUp Test",
        "workspace_name": "TaskUp WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    task = await client.post(
        f"/api/v1/workspaces/{workspace_id}/tasks",
        json={"title": "Refactor DB layer", "priority": "medium"},
        headers=headers
    )
    task_id = task.json()["id"]

    updated = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/tasks/{task_id}",
        json={"status": "in_progress"},
        headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_list_tasks(client):
    """Should list tasks in a workspace."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("lstask"),
        "password": "Test1234!",
        "name": "LsTask Test",
        "workspace_name": "LsTask WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        f"/api/v1/workspaces/{workspace_id}/tasks",
        json={"title": "Task Alpha", "priority": "low"},
        headers=headers
    )
    r = await client.get(f"/api/v1/workspaces/{workspace_id}/tasks", headers=headers)
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert "Task Alpha" in titles


@pytest.mark.asyncio
async def test_create_task_from_message(client):
    """Should create a task linked to a source message (message-to-task flow)."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("msgtask"),
        "password": "Test1234!",
        "name": "MsgTask Test",
        "workspace_name": "MsgTask WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    ch = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels",
        json={"name": "dev", "type": "public"},
        headers=headers
    )
    channel_id = ch.json()["id"]

    msg = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels/{channel_id}/messages",
        json={"content": "We should fix the auth bug ASAP"},
        headers=headers
    )
    msg_id = msg.json()["id"]

    task = await client.post(
        f"/api/v1/workspaces/{workspace_id}/tasks",
        json={"title": "Fix auth bug", "priority": "urgent", "source_message_id": msg_id},
        headers=headers
    )
    assert task.status_code in (200, 201)
    assert task.json()["source_message_id"] == msg_id


@pytest.mark.asyncio
async def test_create_document(client):
    """Should be able to create a document."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("doc"),
        "password": "Test1234!",
        "name": "Doc Test",
        "workspace_name": "Doc WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        json={"title": "Product Roadmap", "content": {"type": "doc", "content": []}},
        headers=headers
    )
    assert r.status_code in (200, 201)
    data = r.json()
    assert data["title"] == "Product Roadmap"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_document(client):
    """Should fetch a specific document by ID."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("getdoc"),
        "password": "Test1234!",
        "name": "GetDoc Test",
        "workspace_name": "GetDoc WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        json={"title": "Engineering Spec", "content": {"text": "details"}},
        headers=headers
    )
    doc_id = created.json()["id"]

    fetched = await client.get(
        f"/api/v1/workspaces/{workspace_id}/documents/{doc_id}",
        headers=headers
    )
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Engineering Spec"


@pytest.mark.asyncio
async def test_update_document(client):
    """Should update a document's title."""
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("upddoc"),
        "password": "Test1234!",
        "name": "UpdDoc Test",
        "workspace_name": "UpdDoc WS"
    })
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        json={"title": "Old Title"},
        headers=headers
    )
    doc_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/documents/{doc_id}",
        json={"title": "New Title"},
        headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "New Title"


@pytest.mark.asyncio
async def test_full_collaboration_flow(client):
    """
    Full end-to-end flow:
    signup → create channel → send message → create task from message → create doc.
    """
    # 1. Signup
    signup = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("fullflow"),
        "password": "Test1234!",
        "name": "FullFlow User",
        "workspace_name": "FullFlow Corp"
    })
    assert signup.status_code in (200, 201)
    d = signup.json()
    token, workspace_id = d["token"], d["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create channel
    ch = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels",
        json={"name": "product", "type": "public"},
        headers=headers
    )
    assert ch.status_code in (200, 201)
    channel_id = ch.json()["id"]

    # 3. Send message
    msg = await client.post(
        f"/api/v1/workspaces/{workspace_id}/channels/{channel_id}/messages",
        json={"content": "Launch is tomorrow, need to finalize docs!"},
        headers=headers
    )
    assert msg.status_code in (200, 201)
    msg_id = msg.json()["id"]

    # 4. Create task from message
    task = await client.post(
        f"/api/v1/workspaces/{workspace_id}/tasks",
        json={
            "title": "Finalize launch docs",
            "priority": "urgent",
            "source_message_id": msg_id
        },
        headers=headers
    )
    assert task.status_code in (200, 201)
    assert task.json()["source_message_id"] == msg_id

    # 5. Create document linked to channel
    doc = await client.post(
        f"/api/v1/workspaces/{workspace_id}/documents",
        json={
            "title": "Launch Checklist",
            "content": {"type": "doc", "content": []},
            "linked_channel_id": channel_id
        },
        headers=headers
    )
    assert doc.status_code in (200, 201)
    assert doc.json()["title"] == "Launch Checklist"
