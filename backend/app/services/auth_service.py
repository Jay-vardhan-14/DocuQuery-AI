"""Authentication service — user registration, login, and lookup."""

import logging
from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        password: Plaintext password.

    Returns:
        Bcrypt hash string.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: Plaintext password to verify.
        hashed_password: Bcrypt hash to verify against.

    Returns:
        True if the password matches.
    """
    return pwd_context.verify(plain_password, hashed_password)


async def register_user(
    email: str,
    password: str,
    full_name: str,
    db: AsyncSession,
    role: str = "employee",
) -> User:
    """Register a new user.

    Args:
        email: User's email address (must be unique).
        password: Plaintext password (will be hashed).
        full_name: User's full name.
        db: Async database session.
        role: User role (default: employee).

    Returns:
        The created User object.

    Raises:
        ValueError: If email is already registered.
    """
    # Check for existing user with same email
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        logger.warning("Registration attempt with existing email: %s", email)
        raise ValueError(f"Email already registered: {email}")

    # Create new user
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("User registered: email=%s, role=%s", email, role)
    return user


async def authenticate_user(
    email: str,
    password: str,
    db: AsyncSession,
) -> User | None:
    """Authenticate a user by email and password.

    Args:
        email: User's email address.
        password: Plaintext password to verify.
        db: Async database session.

    Returns:
        The User object if credentials are valid, None otherwise.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # DEBUG: See what users exist
    all_users = (await db.execute(select(User))).scalars().all()
    logger.error(f"DEBUG users in db: {[u.email for u in all_users]}, looking for {email}")

    if user is None:
        logger.warning("Login attempt for non-existent email: %s", email)
        return None

    if not user.is_active:
        logger.warning("Login attempt for deactivated user: %s", email)
        return None

    if not verify_password(password, user.password_hash):
        logger.warning("Login attempt with wrong password: %s", email)
        return None

    logger.info("User authenticated: %s", email)
    return user


async def get_user_by_id(user_id: UUID, db: AsyncSession) -> User | None:
    """Look up a user by their UUID.

    Args:
        user_id: The user's UUID.
        db: Async database session.

    Returns:
        The User object if found, None otherwise.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
