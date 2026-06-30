"""Tests for authentication endpoints.

Covers: registration, login, token refresh, /me, and error cases.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient

from tests.conftest import create_user

pytestmark = pytest.mark.asyncio


class TestRegister:
    """Tests for POST /api/v1/auth/register."""

    async def test_register_success(self, client: AsyncClient):
        """Registering with valid data returns 201 and tokens."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepass123",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_duplicate_email(self, client: AsyncClient, db_session):
        """Registering with an existing email returns 400."""
        # Create a user first
        await create_user(db_session, email="duplicate@example.com")

        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "securepass123",
                "full_name": "Duplicate User",
            },
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_invalid_email(self, client: AsyncClient):
        """Registering with an invalid email returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "securepass123",
                "full_name": "Bad Email User",
            },
        )
        assert response.status_code == 422

    async def test_register_short_password(self, client: AsyncClient):
        """Registering with a too-short password returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "shortpass@example.com",
                "password": "short",
                "full_name": "Short Pass",
            },
        )
        assert response.status_code == 422

    async def test_register_missing_fields(self, client: AsyncClient):
        """Registering with missing required fields returns 422."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "nopass@example.com"},
        )
        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(self, client: AsyncClient, db_session):
        """Login with valid credentials returns tokens."""
        await create_user(
            db_session,
            email="loginuser@example.com",
            password="password123",
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "loginuser@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, db_session):
        """Login with wrong password returns 401."""
        await create_user(
            db_session,
            email="wrongpass@example.com",
            password="correctpassword",
        )

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Login with non-existent email returns 401."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401

    async def test_login_deactivated_user(self, client: AsyncClient, db_session):
        """Login with a deactivated account returns 401."""
        user = await create_user(
            db_session,
            email="deactivated@example.com",
            password="password123",
        )
        user.is_active = False
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "deactivated@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401


class TestTokenRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    async def test_refresh_success(self, client: AsyncClient, db_session):
        """Valid refresh token returns new tokens."""
        await create_user(
            db_session,
            email="refreshuser@example.com",
            password="password123",
        )

        # Login first to get a refresh token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "refreshuser@example.com",
                "password": "password123",
            },
        )
        refresh_token = login_response.json()["refresh_token"]

        # Use refresh token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Invalid refresh token returns 401."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == 401

    async def test_refresh_with_access_token(self, client: AsyncClient, db_session):
        """Using an access token as refresh token returns 401."""
        await create_user(
            db_session,
            email="accessasrefresh@example.com",
            password="password123",
        )

        login_response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "accessasrefresh@example.com",
                "password": "password123",
            },
        )
        access_token = login_response.json()["access_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == 401
        assert "refresh" in response.json()["detail"].lower()


class TestMe:
    """Tests for GET /api/v1/auth/me."""

    async def test_me_authenticated(self, admin_client: AsyncClient, admin_user):
        """Authenticated user gets their profile."""
        response = await admin_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == admin_user.email
        assert data["full_name"] == admin_user.full_name
        assert data["role"] == "admin"
        assert data["is_active"] is True
        assert "id" in data
        assert "created_at" in data

    async def test_me_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request to /me returns 401/403."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    async def test_me_invalid_token(self, client: AsyncClient):
        """Request with invalid token returns 401/403."""
        client.headers["Authorization"] = "Bearer invalid.jwt.token"
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    async def test_me_employee_role(self, employee_client: AsyncClient, employee_user):
        """Employee user gets their profile with correct role."""
        response = await employee_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "employee"

    async def test_me_manager_role(self, manager_client: AsyncClient, manager_user):
        """Manager user gets their profile with correct role."""
        response = await manager_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "manager"


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    async def test_health_simple(self, client: AsyncClient):
        """Simple health check returns healthy."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    async def test_health_detailed(self, client: AsyncClient):
        """Detailed health check returns component statuses."""
        response = await client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "database" in data["components"]
        assert "redis" in data["components"]
