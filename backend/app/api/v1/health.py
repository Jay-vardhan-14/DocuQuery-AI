"""Health check API endpoints.

Provides simple and detailed health checks for monitoring.
"""

import logging

from fastapi import APIRouter, status
from redis.asyncio import Redis
from sqlalchemy import text

from app.database import engine
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Simple health check",
)
async def health_check() -> dict:
    """Return a simple health status.

    Used by Docker health checks and load balancers.
    """
    return {"status": "healthy"}


@router.get(
    "/detailed",
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
)
async def detailed_health_check() -> dict:
    """Return detailed health status including all dependencies.

    Checks connectivity to PostgreSQL and Redis.
    """
    health = {
        "status": "healthy",
        "components": {
            "database": {"status": "unknown"},
            "redis": {"status": "unknown"},
        },
    }

    # Check database
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        health["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        logger.error("Database health check failed: %s", str(e))
        health["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check Redis
    try:
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis.ping()
        await redis.aclose()
        health["components"]["redis"] = {"status": "healthy"}
    except Exception as e:
        logger.error("Redis health check failed: %s", str(e))
        health["components"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    return health
