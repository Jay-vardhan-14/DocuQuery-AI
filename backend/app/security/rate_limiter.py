"""Redis-based sliding window rate limiter.

Enforces per-user request limits using a Redis sorted set
with timestamp-based sliding window.
"""

import logging
import time
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

# Redis client (initialized lazily)
_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create the Redis client connection."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


async def check_rate_limit(user_id: UUID) -> None:
    """Check if a user has exceeded the rate limit.

    Uses a Redis sorted set with timestamps as scores to implement
    a sliding window rate limiter.

    Args:
        user_id: The user's UUID.

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded.
    """
    redis = await get_redis()
    key = f"rate_limit:{user_id}"
    now = time.time()
    window_start = now - 60  # 1-minute sliding window

    pipe = redis.pipeline()

    # Remove entries outside the window
    pipe.zremrangebyscore(key, 0, window_start)

    # Count entries in the current window
    pipe.zcard(key)

    # Add current request
    pipe.zadd(key, {str(now): now})

    # Set expiry on the key (cleanup)
    pipe.expire(key, 120)

    results = await pipe.execute()
    request_count = results[1]

    if request_count >= settings.RATE_LIMIT_PER_MINUTE:
        logger.warning(
            "Rate limit exceeded for user %s: %d requests in window",
            user_id,
            request_count,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum {limit} requests per minute.".format(
                limit=settings.RATE_LIMIT_PER_MINUTE
            ),
            headers={"Retry-After": "60"},
        )
