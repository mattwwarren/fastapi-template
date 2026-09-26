"""@cached decorator for the cache-aside pattern.

Both the identifier and the tenant are resolved **explicitly** from the
decorated function's own kwargs (``id_param`` / ``tenant_param``) -- there is no
ambient request-context auto-detection. The tenant value may be a
``TenantContext`` (threaded through as ``tenant=``) or a bare organization id
(threaded through as ``organization_id=``).

Missing either kwarg is treated as decorator misconfiguration: the wrapper logs
a warning and calls through uncached (fail-open). This is distinct from the
fail-closed-by-construction guarantee at the ``TenantContext`` level -- caching
is a performance optimization, not a security boundary.

Because values are read from ``kwargs`` only, a positional call would silently
bypass the cache. To make that misuse loud, ``id_param``, ``tenant_param`` and
``redis`` -- when present in the decorated function's signature -- must be
declared keyword-only (after a bare ``*``); otherwise decoration raises
``TypeError``.
"""

from __future__ import annotations

import functools
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast
from uuid import UUID

from fastapi_template.cache.client import cache_get, cache_set
from fastapi_template.core.tenants import TenantContext

if TYPE_CHECKING:
    from pydantic import BaseModel
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


def _require_keyword_only(func: Callable[..., object], param_name: str) -> None:
    """Raise ``TypeError`` if ``param_name`` is in ``func``'s signature but not keyword-only.

    Params absent from the signature are left alone: that path is the
    existing "missing kwarg -> warn + call through uncached" misconfiguration.
    """
    param = inspect.signature(func).parameters.get(param_name)
    if param is not None and param.kind is not inspect.Parameter.KEYWORD_ONLY:
        msg = (
            f"@cached: {func.__name__!r} parameter {param_name!r} must be keyword-only "
            "(add a bare '*' before it in the signature) -- a positional call would "
            "silently disable caching."
        )
        raise TypeError(msg)


def cached(
    resource_type: str,
    tenant_param: str = "tenant",
    id_param: str = "id",
    ttl: int | None = None,
    model_class: type[BaseModel] | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate a service function with cache-aside behavior.

    Args:
        resource_type: Entity type for the cache key (user, organization, ...).
        tenant_param: Name of the kwarg carrying the tenant (``TenantContext``)
            or organization id. Default: ``"tenant"``.
        id_param: Name of the kwarg carrying the identifier. Default: ``"id"``.
        ttl: Cache TTL in seconds (``None`` uses the configured default).
        model_class: Optional Pydantic model class for typed deserialization.

    Returns:
        A decorator wrapping the target coroutine function.

    Notes:
        - The decorated function MUST accept a ``redis`` kwarg (``RedisDep``).
        - ``id_param``, ``tenant_param`` and ``redis`` must be keyword-only
          (declared after a bare ``*``); decoration raises ``TypeError``
          otherwise.
        - Only non-``None`` results are cached.
        - Missing ``tenant_param``/``id_param`` -> warn + call through uncached.
        - Gracefully degrades to a direct call when Redis is unavailable.

    Raises:
        TypeError: At decoration time, if ``id_param``, ``tenant_param`` or
            ``redis`` is in the decorated function's signature but not
            keyword-only.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        for param_name in (id_param, tenant_param, "redis"):
            _require_keyword_only(func, param_name)

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            redis = cast("Redis | None", kwargs.get("redis"))
            identifier = kwargs.get(id_param)
            tenant_value = kwargs.get(tenant_param)

            if not identifier or tenant_value is None:
                logger.warning(
                    "Cache decorator: missing %r/%r in kwargs for %s, skipping cache",
                    id_param,
                    tenant_param,
                    func.__name__,
                )
                return await func(*args, **kwargs)

            if isinstance(tenant_value, TenantContext):
                tenant_ctx: TenantContext | None = tenant_value
                org_id: UUID | str | None = None
            elif isinstance(tenant_value, (UUID, str)):
                tenant_ctx, org_id = None, tenant_value
            else:
                logger.warning(
                    "Cache decorator: %r is not a TenantContext/UUID/str for %s, skipping cache",
                    tenant_param,
                    func.__name__,
                )
                return await func(*args, **kwargs)

            cached_value = await cache_get(
                redis,
                resource_type=resource_type,
                identifier=str(identifier),
                model_class=model_class,
                tenant=tenant_ctx,
                organization_id=org_id,
            )
            if cached_value is not None:
                return cast("T", cached_value)

            result = await func(*args, **kwargs)

            if result is not None:
                await cache_set(
                    redis,
                    resource_type=resource_type,
                    identifier=str(identifier),
                    value=cast("BaseModel", result),
                    ttl=ttl,
                    tenant=tenant_ctx,
                    organization_id=org_id,
                )

            return result

        return wrapper

    return decorator
