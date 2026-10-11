import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Override settings before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["COORDINATOR_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-chars-long"
os.environ["WORKER_DEV_AUTH_TOKEN"] = "test-dev-worker-token"
os.environ["WORKER_HEARTBEAT_TIMEOUT_SECONDS"] = "2"

from coordinator.config import settings
from coordinator.db.base import Base
from coordinator.db.session import get_db
from coordinator.main import app
from coordinator.core.security import hash_password, create_access_token
from coordinator.models.user import User

# Test in-memory database engine
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_database():
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async test client bound to FastAPI application."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_auth_headers() -> dict:
    """Create an admin user and return authorization header."""
    async with TestingSessionLocal() as db:
        user = User(
            username="admin_user",
            email="admin@websync.ai",
            hashed_password=hash_password("admin_password_123"),
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    token = create_access_token(subject=user_id, token_type="user", role="admin")
    return {"Authorization": f"Bearer {token}"}
