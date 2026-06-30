"""Test fixtures for DocuQuery AI backend tests.

Provides:
- Async test database setup with fresh tables per test session
- Test client (httpx AsyncClient)
- User creation helpers for each role
- Authenticated client fixtures
"""

import asyncio
from typing import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.database import Base
from app.api.deps import get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import hash_password
from app.security.jwt_handler import create_access_token


from sqlalchemy.pool import NullPool

# Test database URL (uses the same DB with a test schema approach,
# or a separate test DB configured via environment)
TEST_DATABASE_URL = settings.DATABASE_URL.replace("/docuquery", "/test_docuquery")

# Create test engine with NullPool to avoid cross-loop connection pooling
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)





@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Reset the database before each test."""
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE;"))
        await conn.execute(text("CREATE SCHEMA public;"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with overridden DB dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def create_user(
    db_session: AsyncSession,
    email: str,
    password: str = "password123",
    full_name: str = "Test User",
    role: str = "employee",
) -> User:
    """Helper to create a test user in the database.

    Args:
        db_session: Async database session.
        email: User email.
        password: Plaintext password.
        full_name: User's full name.
        role: User role.

    Returns:
        Created User object.
    """
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user for testing."""
    return await create_user(
        db_session,
        email="testadmin@docuquery.ai",
        full_name="Test Admin",
        role="admin",
    )


@pytest_asyncio.fixture
async def manager_user(db_session: AsyncSession) -> User:
    """Create a manager user for testing."""
    return await create_user(
        db_session,
        email="testmanager@docuquery.ai",
        full_name="Test Manager",
        role="manager",
    )


@pytest_asyncio.fixture
async def employee_user(db_session: AsyncSession) -> User:
    """Create an employee user for testing."""
    return await create_user(
        db_session,
        email="testemployee@docuquery.ai",
        full_name="Test Employee",
        role="employee",
    )


def get_auth_headers(user: User) -> dict:
    """Generate authorization headers with a valid JWT for a user.

    Args:
        user: The User object to create a token for.

    Returns:
        Dictionary with Authorization header.
    """
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_client(
    client: AsyncClient,
    admin_user: User,
) -> AsyncClient:
    """Provide an authenticated client with admin privileges."""
    client.headers.update(get_auth_headers(admin_user))
    return client


@pytest_asyncio.fixture
async def manager_client(
    client: AsyncClient,
    manager_user: User,
) -> AsyncClient:
    """Provide an authenticated client with manager privileges."""
    client.headers.update(get_auth_headers(manager_user))
    return client


@pytest_asyncio.fixture
async def employee_client(
    client: AsyncClient,
    employee_user: User,
) -> AsyncClient:
    """Provide an authenticated client with employee privileges."""
    client.headers.update(get_auth_headers(employee_user))
    return client
