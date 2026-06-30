"""FastAPI dependency injection providers.

Provides reusable dependencies for database sessions, authentication,
and role-based access control checks.
"""

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.user import User
from app.security.jwt_handler import JWTError, verify_token
from app.services.auth_service import get_user_by_id

logger = logging.getLogger(__name__)

# Bearer token extraction scheme
security_scheme = HTTPBearer()


async def get_db() -> AsyncSession:
    """Provide an async database session.

    Yields:
        An async SQLAlchemy session that auto-closes after use.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and verify the JWT from the Authorization header.

    Returns the authenticated User object.

    Args:
        credentials: Bearer token from the Authorization header.
        db: Async database session.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException: 401 if token is invalid or user not found.
    """
    try:
        payload = verify_token(credentials.credentials)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(UUID(user_id), db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that requires the current user to be an admin.

    Args:
        current_user: The authenticated user.

    Returns:
        The admin User object.

    Raises:
        HTTPException: 403 if user is not an admin.
    """
    if current_user.role != "admin":
        logger.warning(
            "Non-admin user %s attempted admin-only action",
            current_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_manager_or_above(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that requires manager or admin role.

    Args:
        current_user: The authenticated user.

    Returns:
        The User object (manager or admin).

    Raises:
        HTTPException: 403 if user is not a manager or admin.
    """
    if current_user.role not in ("admin", "manager"):
        logger.warning(
            "User %s (role=%s) attempted manager+ action",
            current_user.email,
            current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required",
        )
    return current_user
