"""
Shared pytest fixtures for LNO OS API tests.

Uses a session-scoped event loop so all async tests share one loop — this avoids
asyncpg "operation in progress" / "attached to a different loop" errors that occur
when each test function gets its own loop while the connection pool holds references
to a prior loop.
"""
import asyncio
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient, ASGITransport
from main import app
from db.session import get_db
from core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop shared across the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    """Session-scoped async engine with NullPool (no connection reuse)."""
    engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(db_engine):
    """AsyncClient per test, with dependency-injected DB session."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
