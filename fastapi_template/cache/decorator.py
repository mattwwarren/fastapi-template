"""@cached decorator for cache-aside pattern."""

from __future__ import annotations

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from fastapi_template.cache.client import cache_get, cache_set

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


def cached(
    resource_type: str,
    id_param: str = "id",
    ttl: int | None = None,
    model_class: type[BaseModel] | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for cache-aside pattern on service functions.

    Automatically handles cache lookups and population for service functions
    that fetch entities by ID.

    Args:
        resource_type: Entity type for cache key (user, organization, etc.)
        id_param: Parameter name containing the identifier (default: "id")
        ttl: Cache TTL in seconds (None uses default)
        model_class: Optional Pydantic model class for typed deserialization

    Returns:
        Decorated function with automatic caching

    Usage:
        # Basic usage
        @cached("user", id_param="user_id", model_class=User)
        async def get_user(
            session: AsyncSession,
            user_id: UUID,
            redis: RedisDep,  # Must have redis parameter
        ) -> User | None:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

        # With custom TTL (30 minutes)
        @cached("organization", id_param="org_id", ttl=1800)
        async def get_organization(
            session: AsyncSession,
            org_id: UUID,
            redis: RedisDep,
        ) -> Organization | None:
            ...

    Cache flow:
        1. Extract identifier from function kwargs
        2. Check cache (cache_get)
        3. On miss: call function, cache result (cache_set)
        4. Return result

    Note:
        - Decorated function MUST have a `redis` parameter (RedisDep)
        - Cache key is built using resource_type + identifier
        - Only caches non-None results
        - Gracefully degrades if Redis unavailable
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Extract Redis client from kwargs (injected via RedisDep)
            redis = kwargs.get("redis")

            # Extract identifier from kwargs
            identifier = kwargs.get(id_param)
            if not identifier:
                logger.warning(
                    "Cache decorator: %s not found in kwargs for %s, skipping cache",
                    id_param,
                    func.__name__,
                )
                return await func(*args, **kwargs)

            # Attempt cache hit
            cached_value = await cache_get(redis, resource_type, str(identifier), model_class)  # type: ignore[arg-type]
            if cached_value is not None:
                return cached_value  # type: ignore[return-value]

            # Cache miss - call function
            result = await func(*args, **kwargs)

            # Cache the result (fire-and-forget, don't block on cache failure)
            if result is not None:
                await cache_set(redis, resource_type, str(identifier), result, ttl)  # type: ignore[arg-type]

            return result

        return wrapper

    return decorator
