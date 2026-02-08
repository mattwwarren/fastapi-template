"""Redis caching utilities with multi-tenancy support.

Public API for cache operations in the application.

Examples:
    # Explicit caching
    from fastapi_template.cache import cache_get, cache_set, cache_delete

    cached_user = await cache_get(redis, "user", user_id, User)
    await cache_set(redis, "user", user_id, user_obj, ttl=1800)
    await cache_delete(redis, "user", user_id)

    # Decorator caching
    from fastapi_template.cache import cached

    @cached("user", id_param="user_id", model_class=User)
    async def get_user(session: AsyncSession, user_id: UUID, redis: RedisDep):
        ...

    # Cache key building
    from fastapi_template.cache import build_cache_key

    key = build_cache_key("user", user_id, tenant_id=org_id)
"""

from fastapi_template.cache.client import cache_delete, cache_get, cache_set
from fastapi_template.cache.decorator import cached
from fastapi_template.cache.exceptions import (
    CacheConnectionError,
    CacheError,
    CacheSerializationError,
)
from fastapi_template.cache.keys import build_cache_key
from fastapi_template.cache.serialization import deserialize, serialize

__all__ = [
    # High-level operations
    "cache_get",
    "cache_set",
    "cache_delete",
    # Decorator
    "cached",
    # Utilities
    "build_cache_key",
    "serialize",
    "deserialize",
    # Exceptions
    "CacheError",
    "CacheSerializationError",
    "CacheConnectionError",
]
