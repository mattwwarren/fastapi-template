"""Redis caching utilities with multi-tenant key isolation.

Public API for cache operations. Tenant scoping is always threaded explicitly
(``tenant`` / ``organization_id``); there is no ambient auto-detection.

Examples:
    # Explicit caching
    from fastapi_template.cache import cache_get, cache_set, cache_delete

    # Cache a non-PII projection (e.g. UserSummary: id + name), never a
    # pii=True model such as User -- cache_set raises CachePiiViolationError.
    cached_summary = await cache_get(redis, "user", user_id, UserSummary, tenant=tenant)
    await cache_set(redis, "user", user_id, summary, ttl=1800, tenant=tenant)
    await cache_delete(redis, "user", user_id, tenant=tenant)

    # Decorator caching
    from fastapi_template.cache import cached

    # tenant/user_id/redis must be keyword-only (after a bare ``*``).
    @cached("user", tenant_param="tenant", id_param="user_id", model_class=UserSummary)
    async def get_user(session: AsyncSession, *, tenant: TenantContext, user_id: UUID, redis: RedisDep):
        ...

    # Cache key building
    from fastapi_template.cache import build_cache_key

    key = build_cache_key("user", user_id, organization_id=org_id)
"""

from fastapi_template.cache.client import (
    RedisDep,
    cache_delete,
    cache_get,
    cache_set,
    create_redis_client,
)
from fastapi_template.cache.decorator import cached
from fastapi_template.cache.exceptions import CacheError, CachePiiViolationError, CacheSerializationError
from fastapi_template.cache.keys import build_cache_key
from fastapi_template.cache.serialization import deserialize, serialize

__all__ = [
    # Exceptions
    "CacheError",
    "CachePiiViolationError",
    "CacheSerializationError",
    # Dependency
    "RedisDep",
    # Utilities
    "build_cache_key",
    "cache_delete",
    # High-level operations
    "cache_get",
    "cache_set",
    # Decorator
    "cached",
    # Connection factory
    "create_redis_client",
    "deserialize",
    "serialize",
]
