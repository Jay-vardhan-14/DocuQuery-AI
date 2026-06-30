"""JWT token creation and verification."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.config import settings

logger = logging.getLogger(__name__)


class JWTError(Exception):
    """Custom exception for JWT-related errors."""
    pass


def create_access_token(user_id: UUID, role: str) -> str:
    """Create a JWT access token with user ID and role claims.

    Args:
        user_id: The user's UUID.
        role: The user's role (admin, manager, employee).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def create_refresh_token(user_id: UUID) -> str:
    """Create a JWT refresh token.

    Args:
        user_id: The user's UUID.

    Returns:
        Encoded JWT refresh token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token.

    Args:
        token: The encoded JWT string.

    Returns:
        Decoded payload dictionary.

    Raises:
        JWTError: If the token is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise JWTError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token: %s", str(e))
        raise JWTError("Invalid token")
