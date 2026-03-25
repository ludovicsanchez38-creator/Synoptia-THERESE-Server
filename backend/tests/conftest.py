"""
THERESE v2 - Backend Test Configuration

Pytest fixtures and configuration for backend tests.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Set test environment before importing app
os.environ["THERESE_ENV"] = "test"
os.environ["THERESE_DB_PATH"] = ":memory:"

from app.main import app
from app.models.database import get_session

# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

async_session_maker = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_maker() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with database session override."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# Alias for compatibility
@pytest_asyncio.fixture(scope="function")
async def client(async_client: AsyncClient) -> AsyncGenerator[AsyncClient, None]:
    """Alias for async_client."""
    yield async_client


@pytest.fixture
def sync_client() -> TestClient:
    """Create synchronous test client for simple tests."""
    return TestClient(app)



@pytest_asyncio.fixture(scope="function")
async def authenticated_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with a valid JWT token (mock admin)."""
    from jose import jwt
    from datetime import datetime, timedelta
    from app.config import settings

    # Generate a valid JWT token
    payload = {
        "sub": "test-admin-id",
        "email": "admin@test.org",
        "name": "Admin Test",
        "role": "admin",
        "org_id": "test-org-id",
        "charter_accepted": True,
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    # Override get_current_user to avoid DB lookup
    from app.auth.rbac import get_current_user

    mock_user = type("MockUser", (), {
        "id": "test-admin-id",
        "email": "admin@test.org",
        "name": "Admin Test",
        "role": "admin",
        "org_id": "test-org-id",
        "is_active": True,
        "is_verified": True,
        "is_superuser": True,
        "charter_accepted": True,
    })()

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
