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
from redis.asyncio import BlockingConnectionPool, Redis

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
# Set by create_redis_client() as a side effect (mirrors realtime/server.py's
# own `global _sio, _sio_app` convention for init_sio()). For new code, prefer
# the RedisDep dependency; this global supports fire-and-forget usage without
# request context.
redis_client: Redis | None = None


def _log_cache_failure(operation: str, resource_type: str, identifier: str, exc: Exception) -> None:
    logger.warning("Cache %s failed for %s:%s - %s", operation, resource_type, identifier, exc)


async def create_redis_client() -> Redis | None:
    """Create a Redis client with a connection pool, or None if disabled.

    Follows the same enablement convention as ``realtime.server.init_sio``:
    an unset ``REDIS_URL`` means the feature is disabled (returns ``None``).
    A connection failure is logged and also yields ``None`` (graceful
    degradation) -- this function never raises into its caller.

    As a side effect, updates the module-level ``redis_client`` global so that
    ``get_redis()``/``RedisDep`` reflect the current connection state -- this
    is the single source of truth for the DI path, regardless of what the
    caller (e.g. main.py's lifespan) also stores on ``app.state``.

    Returns:
        A connected Redis client, or None if Redis is unset/unreachable.
    """
    global redis_client  # noqa: PLW0603 - mirrors realtime/server.py's init_sio() convention

    if not settings.redis_url:
        logger.warning("Redis caching disabled (REDIS_URL not set) - cache operations will be no-ops")
        redis_client = None
        return None

    client: Redis | None = None
    try:
        pool = BlockingConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_pool_size,
            timeout=settings.redis_pool_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            socket_timeout=settings.redis_socket_timeout,
        )
        client = Redis(connection_pool=pool, decode_responses=True)
        await client.ping()
    except Exception:
        logger.exception("Failed to connect to Redis - caching disabled")
        if client is not None:
            await client.aclose()
        redis_client = None
        return None

    # Redact credentials from URL before logging.
    safe_url = settings.redis_url.split("@")[-1]
    logger.info("Redis connection successful: %s", safe_url)
    redis_client = client
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

    start = time.perf_counter()
    try:
        data = await redis.get(key)
    except Exception as exc:
        cache_operation_duration_seconds.labels(operation="get").observe(time.perf_counter() - start)
        _log_cache_failure("get", resource_type, identifier, exc)
        cache_misses_total.labels(resource_type=resource_type).inc()
        return None
    cache_operation_duration_seconds.labels(operation="get").observe(time.perf_counter() - start)

    if not data:
        cache_misses_total.labels(resource_type=resource_type).inc()
        return None

    try:
        result = deserialize(data, model_class)
    except CacheSerializationError as exc:
        _log_cache_failure("deserialize", resource_type, identifier, exc)
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

    start = time.perf_counter()
    try:
        data = serialize(value)
        await redis.setex(key, ttl, data)
    except Exception as exc:
        cache_operation_duration_seconds.labels(operation="set").observe(time.perf_counter() - start)
        _log_cache_failure("set", resource_type, identifier, exc)
        return False
    else:
        cache_operation_duration_seconds.labels(operation="set").observe(time.perf_counter() - start)
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

    start = time.perf_counter()
    try:
        await redis.delete(key)
    except Exception as exc:
        cache_operation_duration_seconds.labels(operation="delete").observe(time.perf_counter() - start)
        _log_cache_failure("delete", resource_type, identifier, exc)
        return False
    else:
        cache_operation_duration_seconds.labels(operation="delete").observe(time.perf_counter() - start)
        return True
