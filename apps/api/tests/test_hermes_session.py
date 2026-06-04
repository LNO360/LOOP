"""Tests for Hermes chat session — clear endpoint and prefix injection."""
import uuid
import pytest
from httpx import AsyncClient


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


async def _signup_and_auth(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/api/v1/auth/signup", json={
        "email": _unique_email("sessiontest"),
        "password": "pass123",
        "name": "Session Tester",
        "workspace_name": "Session Corp",
    })
    data = resp.json()
    return data["token"], data["workspace_id"]


@pytest.mark.asyncio
async def test_delete_session_clears_nonexistent_gracefully(client):
    token, workspace_id = await _signup_and_auth(client)
    resp = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/hermes/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_delete_session_clears_existing_session(client):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from core.config import settings
    from models.ai_chat import HermesChatSession
    from sqlalchemy import select

    token, workspace_id = await _signup_and_auth(client)

    # Manually insert a session row
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        from models.workspace import Workspace
        ws = (await db.execute(
            select(Workspace).where(Workspace.id == uuid.UUID(workspace_id))
        )).scalar_one()
        session_row = HermesChatSession(
            workspace_id=uuid.UUID(workspace_id),
            user_id=ws.owner_id,
            agent_slug=None,
            summary="• Some old summary",
            raw_tail=[{"user": "hi", "hermes": "hello"}],
            message_count=1,
        )
        db.add(session_row)
        await db.commit()
    await engine.dispose()

    # Now delete via API
    resp = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/hermes/session",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Verify cleared
    engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory2 = async_sessionmaker(engine2, expire_on_commit=False)
    async with session_factory2() as db:
        row = (await db.execute(
            select(HermesChatSession).where(
                HermesChatSession.workspace_id == uuid.UUID(workspace_id)
            )
        )).scalar_one_or_none()
        assert row is None
    await engine2.dispose()


@pytest.mark.asyncio
async def test_update_session_appends_exchange_and_triggers_compression():
    """_update_session appends exchange; triggers compress when raw_tail chars > 3000."""
    from unittest.mock import AsyncMock, patch, MagicMock
    from routers.hermes_chat import _update_session

    # --- Under threshold: no compression ---
    db_under = AsyncMock()
    db_under.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=lambda: None))
    db_under.add = AsyncMock()
    db_under.commit = AsyncMock()

    short_exchange = {"user": "hi", "hermes": "hello"}

    with patch("routers.hermes_chat.compress_and_extract", new_callable=AsyncMock) as mock_compress:
        await _update_session(db_under, "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", None, short_exchange)
        mock_compress.assert_not_awaited()

    # --- Over threshold: compression fires ---
    big_exchange = {"user": "x" * 1500, "hermes": "y" * 1500}
    existing_session = MagicMock()
    existing_session.summary = "old"
    existing_session.raw_tail = [big_exchange]
    existing_session.message_count = 1

    db_over = AsyncMock()
    db_over.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=lambda: existing_session))
    db_over.commit = AsyncMock()

    with patch("routers.hermes_chat.compress_and_extract", new_callable=AsyncMock, return_value="new summary") as mock_compress2:
        await _update_session(db_over, "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002", None, big_exchange)
        mock_compress2.assert_awaited_once()
        assert existing_session.summary == "new summary"
        assert len(existing_session.raw_tail) <= 3
