"""Redis caching utilities with multi-tenant key isolation.

Public API for cache operations. Tenant scoping is always threaded explicitly
(``tenant`` / ``organization_id``); there is no ambient auto-detection.

Examples:
    # Explicit caching
    from fastapi_template.cache import cache_get, cache_set, cache_delete

    cached_user = await cache_get(redis, "user", user_id, User, tenant=tenant)
    await cache_set(redis, "user", user_id, user_obj, ttl=1800, tenant=tenant)
    await cache_delete(redis, "user", user_id, tenant=tenant)

    # Decorator caching
    from fastapi_template.cache import cached

    @cached("user", tenant_param="tenant", id_param="user_id", model_class=User)
    async def get_user(session: AsyncSession, tenant: TenantContext, user_id: UUID, redis: RedisDep):
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
from fastapi_template.cache.exceptions import CacheError, CacheSerializationError
from fastapi_template.cache.keys import build_cache_key
from fastapi_template.cache.serialization import deserialize, serialize

__all__ = [
    # Exceptions
    "CacheError",
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
