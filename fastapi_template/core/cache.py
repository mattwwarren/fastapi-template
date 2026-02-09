"""Redis connection pool factory and dependency injection."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends
from redis.asyncio import ConnectionPool, Redis

from fastapi_template.core.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Module-level Redis client for application-wide access.
# This is updated by:
# - main.py lifespan (sets to actual Redis client on startup)
# - tests/conftest.py (test fixtures update this to point to test Redis)
#
# For new code, prefer using the RedisDep dependency injection.
# This global exists for fire-and-forget operations without request context.
redis_client: Redis | None = None


async def create_redis_client() -> Redis | None:
    """Factory function to create Redis client with connection pool.

    Returns None if Redis is disabled (graceful degradation).

    Returns:
        Redis client or None if disabled

    Raises:
        ConnectionError: If Redis connection fails during initialization
    """
    if not settings.redis_enabled:
        logger.warning("Redis caching is disabled (REDIS_ENABLED=false)")
        return None

    try:
        pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        client: Redis = Redis(connection_pool=pool, decode_responses=True)

        # Validate connectivity
        await client.ping()  # type: ignore[misc]
    except Exception:
        logger.exception("Failed to connect to Redis. Caching disabled.")
        return None

    # Redact password from URL for logging
    safe_url = settings.redis_url.split("@")[-1] if "@" in settings.redis_url else settings.redis_url
    logger.info("Redis connection successful: %s", safe_url)
    return client


async def get_redis() -> AsyncGenerator[Redis | None]:
    """Dependency injection for Redis client.

    Yields the module-level redis_client set during lifespan.
    If Redis is unavailable, yields None (graceful degradation).

    Yields:
        Redis client or None if disabled/unavailable
    """
    yield redis_client


RedisDep = Annotated[Redis | None, Depends(get_redis)]
