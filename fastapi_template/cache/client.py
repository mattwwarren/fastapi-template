"""High-level cache operations with graceful degradation."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, TypeVar

from fastapi_template.cache.keys import build_cache_key
from fastapi_template.cache.serialization import deserialize, serialize
from fastapi_template.core.config import settings

if TYPE_CHECKING:
    from pydantic import BaseModel
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)
T = TypeVar("T", bound="BaseModel")


async def cache_get(
    redis: Redis | None,
    resource_type: str,
    identifier: str,
    model_class: type[T] | None = None,
) -> T | Any | None:
    """Get value from cache with graceful degradation.

    Returns None on cache miss OR if Redis is unavailable.

    Args:
        redis: Redis client (None if disabled)
        resource_type: Entity type (user, organization, etc.)
        identifier: Resource identifier
        model_class: Optional Pydantic model class for deserialization

    Returns:
        Cached value or None

    Examples:
        # Get dict
        result = await cache_get(redis, "user", user_id)

        # Get Pydantic model
        user = await cache_get(redis, "user", user_id, User)
    """
    if not redis:
        return None

    key = build_cache_key(resource_type, identifier)

    try:
        # Import metrics here to avoid circular dependency
        from fastapi_template.core.metrics import (
            cache_hits_total,
            cache_misses_total,
            cache_operation_duration_seconds,
        )

        start = time.perf_counter()
        data = await redis.get(key)
        duration = time.perf_counter() - start

        cache_operation_duration_seconds.labels(operation="get").observe(duration)

        if data:
            cache_hits_total.labels(resource_type=resource_type).inc()
            return deserialize(data, model_class)
        else:
            cache_misses_total.labels(resource_type=resource_type).inc()
            return None

    except Exception as exc:
        logger.warning("Cache get failed for %s:%s - %s. Falling back to database.", resource_type, identifier, exc)
        # Import metrics here to avoid circular dependency
        from fastapi_template.core.metrics import cache_misses_total

        cache_misses_total.labels(resource_type=resource_type).inc()
        return None


async def cache_set(
    redis: Redis | None,
    resource_type: str,
    identifier: str,
    value: Any,
    ttl: int | None = None,
) -> bool:
    """Set value in cache with TTL.

    Args:
        redis: Redis client (None if disabled)
        resource_type: Entity type (user, organization, etc.)
        identifier: Resource identifier
        value: Value to cache (Pydantic model, dict, etc.)
        ttl: Time-to-live in seconds (None uses default)

    Returns:
        True if successful, False otherwise

    Examples:
        # Cache with default TTL
        await cache_set(redis, "user", user_id, user_obj)

        # Cache with custom TTL (30 minutes)
        await cache_set(redis, "user", user_id, user_obj, ttl=1800)
    """
    if not redis:
        return False

    key = build_cache_key(resource_type, identifier)
    ttl = ttl or settings.redis_default_ttl

    try:
        # Import metrics here to avoid circular dependency
        from fastapi_template.core.metrics import cache_operation_duration_seconds

        start = time.perf_counter()
        data = serialize(value)
        await redis.setex(key, ttl, data)
        duration = time.perf_counter() - start

        cache_operation_duration_seconds.labels(operation="set").observe(duration)
        return True

    except Exception as exc:
        logger.warning("Cache set failed for %s:%s - %s", resource_type, identifier, exc)
        return False


async def cache_delete(
    redis: Redis | None,
    resource_type: str,
    identifier: str,
) -> bool:
    """Delete value from cache.

    Used for cache invalidation on updates/deletes.

    Args:
        redis: Redis client (None if disabled)
        resource_type: Entity type (user, organization, etc.)
        identifier: Resource identifier

    Returns:
        True if successful, False otherwise

    Examples:
        # Invalidate cache on update
        await cache_delete(redis, "user", user_id)
    """
    if not redis:
        return False

    key = build_cache_key(resource_type, identifier)

    try:
        # Import metrics here to avoid circular dependency
        from fastapi_template.core.metrics import cache_operation_duration_seconds

        start = time.perf_counter()
        await redis.delete(key)
        duration = time.perf_counter() - start

        cache_operation_duration_seconds.labels(operation="delete").observe(duration)
        return True

    except Exception as exc:
        logger.warning("Cache delete failed for %s:%s - %s", resource_type, identifier, exc)
        return False
