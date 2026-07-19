"""Redis connection factory, dependency injection, and cache operations.

This module owns both the Redis connection lifecycle (``create_redis_client`` /
``get_redis`` / ``RedisDep`` / the module-level ``redis_client``) and the
high-level cache operations (``cache_get`` / ``cache_set`` / ``cache_delete``).

Graceful degradation is the guiding principle: a ``None`` client (Redis unset
or unreachable) turns every operation into a silent no-op, and any error from
Redis itself is logged and swallowed rather than propagated into the request
path -- mirroring the "REDIS_URL absent -> feature disabled" convention that
``realtime/server.py`` already uses for Socket.IO.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends
from redis.asyncio import ConnectionPool, Redis

from fastapi_template.cache.exceptions import CacheSerializationError
from fastapi_template.cache.keys import build_cache_key
from fastapi_template.cache.serialization import deserialize, serialize
from fastapi_template.core.config import settings
from fastapi_template.core.metrics import (
    cache_hits_total,
    cache_misses_total,
    cache_operation_duration_seconds,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

    from fastapi_template.core.tenants import TenantContext

logger = logging.getLogger(__name__)

# Module-level Redis client for application-wide access.
# Updated by main.py lifespan (startup) and by test fixtures. For new code,
# prefer the RedisDep dependency; this global supports fire-and-forget usage
# without request context.
redis_client: Redis | None = None


async def create_redis_client() -> Redis | None:
    """Create a Redis client with a connection pool, or None if disabled.

    Follows the same enablement convention as ``realtime.server.init_sio``:
    an unset ``REDIS_URL`` means the feature is disabled (returns ``None``).
    A connection failure is logged and also yields ``None`` (graceful
    degradation) -- this function never raises into its caller.

    Returns:
        A connected Redis client, or None if Redis is unset/unreachable.
    """
    if not settings.redis_url:
        logger.warning("Redis caching disabled (REDIS_URL not set) - cache operations will be no-ops")
        return None

    try:
        pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        client: Redis = Redis(connection_pool=pool, decode_responses=True)
        await client.ping()
    except Exception:
        logger.exception("Failed to connect to Redis - caching disabled")
        return None

    # Redact credentials from URL before logging.
    safe_url = settings.redis_url.split("@")[-1]
    logger.info("Redis connection successful: %s", safe_url)
    return client


async def get_redis() -> AsyncGenerator[Redis | None]:
    """Dependency injection for the Redis client.

    Yields the module-level ``redis_client`` set during lifespan, or ``None``
    when Redis is unavailable (graceful degradation).
    """
    yield redis_client


RedisDep = Annotated[Redis | None, Depends(get_redis)]


async def cache_get[T: "BaseModel"](  # noqa: PLR0913 - explicit tenant threading (tenant + organization_id) per R1
    redis: Redis | None,
    resource_type: str,
    identifier: str,
    model_class: type[T] | None = None,
    *,
    tenant: TenantContext | None = None,
    organization_id: UUID | str | None = None,
) -> T | dict | list | None:
    """Get a value from cache with graceful degradation.

    Returns ``None`` on cache miss, deserialization failure, Redis error, or a
    ``None`` client. Tenant scoping is threaded explicitly via ``tenant`` /
    ``organization_id``.

    Args:
        redis: Redis client (``None`` if disabled).
        resource_type: Entity type (user, organization, ...).
        identifier: Resource identifier.
        model_class: Optional Pydantic model class for typed deserialization.
        tenant: Tenant context for key scoping.
        organization_id: Explicit organization id for key scoping.

    Returns:
        The cached value (model, dict, or list) or ``None``.
    """
    if not redis:
        return None

    key = build_cache_key(resource_type, identifier, tenant=tenant, organization_id=organization_id)

    try:
        start = time.perf_counter()
        data = await redis.get(key)
        cache_operation_duration_seconds.labels(operation="get").observe(time.perf_counter() - start)
    except Exception as exc:
        logger.warning("Cache %s failed for %s:%s - %s", "get", resource_type, identifier, exc)
        cache_misses_total.labels(resource_type=resource_type).inc()
        return None

    if not data:
        cache_misses_total.labels(resource_type=resource_type).inc()
        return None

    try:
        result = deserialize(data, model_class)
    except CacheSerializationError as exc:
        logger.warning("Cache %s failed for %s:%s - %s", "deserialize", resource_type, identifier, exc)
        cache_misses_total.labels(resource_type=resource_type).inc()
        return None
    else:
        cache_hits_total.labels(resource_type=resource_type).inc()
        return result


async def cache_set(  # noqa: PLR0913 - explicit tenant threading (tenant + organization_id) per R1
    redis: Redis | None,
    resource_type: str,
    identifier: str,
    value: BaseModel,
    ttl: int | None = None,
    *,
    tenant: TenantContext | None = None,
    organization_id: UUID | str | None = None,
) -> bool:
    """Set a value in cache with a TTL.

    Args:
        redis: Redis client (``None`` if disabled).
        resource_type: Entity type (user, organization, ...).
        identifier: Resource identifier.
        value: Value to cache (Pydantic model).
        ttl: Time-to-live in seconds (``None`` uses ``redis_default_ttl``).
        tenant: Tenant context for key scoping.
        organization_id: Explicit organization id for key scoping.

    Returns:
        ``True`` on success, ``False`` otherwise (never raises).
    """
    if not redis:
        return False

    key = build_cache_key(resource_type, identifier, tenant=tenant, organization_id=organization_id)
    ttl = ttl or settings.redis_default_ttl

    try:
        start = time.perf_counter()
        data = serialize(value)
        await redis.setex(key, ttl, data)
        cache_operation_duration_seconds.labels(operation="set").observe(time.perf_counter() - start)
    except Exception as exc:
        logger.warning("Cache %s failed for %s:%s - %s", "set", resource_type, identifier, exc)
        return False
    else:
        return True


async def cache_delete(
    redis: Redis | None,
    resource_type: str,
    identifier: str,
    *,
    tenant: TenantContext | None = None,
    organization_id: UUID | str | None = None,
) -> bool:
    """Delete a value from cache (used for invalidation on writes).

    Args:
        redis: Redis client (``None`` if disabled).
        resource_type: Entity type (user, organization, ...).
        identifier: Resource identifier.
        tenant: Tenant context for key scoping.
        organization_id: Explicit organization id for key scoping.

    Returns:
        ``True`` on success, ``False`` otherwise (never raises).
    """
    if not redis:
        return False

    key = build_cache_key(resource_type, identifier, tenant=tenant, organization_id=organization_id)

    try:
        start = time.perf_counter()
        await redis.delete(key)
        cache_operation_duration_seconds.labels(operation="delete").observe(time.perf_counter() - start)
    except Exception as exc:
        logger.warning("Cache %s failed for %s:%s - %s", "delete", resource_type, identifier, exc)
        return False
    else:
        return True
