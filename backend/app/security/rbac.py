"""Role-based access control logic.

Defines the mapping from user roles to allowed document access levels.
This mapping is used in the vector search WHERE clause to enforce RBAC
at the database query level.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Role → allowed document access levels
# CRITICAL: This mapping is enforced at the SQL query level during vector search
ROLE_ACCESS_MAP: dict[str, List[str]] = {
    "admin": ["public", "internal", "confidential", "restricted"],
    "manager": ["public", "internal", "confidential"],
    "employee": ["public", "internal"],
}

# Valid values for validation
VALID_ROLES = {"admin", "manager", "employee"}
VALID_ACCESS_LEVELS = {"public", "internal", "confidential", "restricted"}


def get_allowed_access_levels(role: str) -> List[str]:
    """Get the document access levels a role is permitted to query.

    Args:
        role: User role (admin, manager, or employee).

    Returns:
        List of access level strings the role can access.

    Raises:
        ValueError: If the role is not recognized.
    """
    if role not in ROLE_ACCESS_MAP:
        logger.error("Unknown role requested: %s", role)
        raise ValueError(f"Unknown role: {role}")
    return ROLE_ACCESS_MAP[role]


def can_access_level(role: str, access_level: str) -> bool:
    """Check if a role can access a specific document access level.

    Args:
        role: User role.
        access_level: Document access level to check.

    Returns:
        True if the role can access the given level.
    """
    allowed = get_allowed_access_levels(role)
    return access_level in allowed
