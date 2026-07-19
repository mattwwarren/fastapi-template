# Redis Caching Guide

Complete guide to using Redis caching in this FastAPI template.

## Overview

This template provides optional Redis caching with:

- **Cache-aside pattern** for read-heavy endpoints
- **Multi-tenant isolation** via cache key namespacing
- **Cross-service compatibility** via JSON serialization
- **Graceful degradation** if Redis is unavailable
- **Observability** via Prometheus metrics

Caching is **enabled by the presence of `REDIS_URL`** (the same variable the
Socket.IO layer uses). When `REDIS_URL` is unset — or Redis is unreachable at
startup — the cache client is `None` and every cache operation becomes a silent
no-op. There is no separate `REDIS_ENABLED` flag.

## Configuration

See [CONFIGURATION-GUIDE.md](../CONFIGURATION-GUIDE.md#redis-caching-configuration)
for environment variables.

## Multi-Tenancy: Explicit Tenant Threading

Cache keys are scoped to a tenant, but the tenant is **always passed
explicitly** — either as a `TenantContext` or as a bare `organization_id`.
There is **no ambient request-context auto-detection** and **no
`ValueError`-on-missing-tenant** behavior.

The fail-closed guarantee comes from *construction*, not from a runtime check:
callers cannot obtain a `TenantContext` without verified organization
membership (see `core/tenants.py`), so a tenant-scoped key can only be built for
a tenant the caller is entitled to. Genuinely global entries (health checks,
system-wide data) pass neither argument and land under the global sentinel
namespace.

```python
from fastapi_template.cache import build_cache_key

# Tenant-scoped via TenantContext
build_cache_key("user", user_id, tenant=tenant)
# → "fastapi_template:tenant-<org_uuid>:user:<user_id>:v1"

# Tenant-scoped via a bare organization_id
build_cache_key("organization", org_id, organization_id=org_id)
# → "fastapi_template:tenant-<org_uuid>:organization:<org_id>:v1"

# Genuinely global (no tenant supplied)
build_cache_key("health", "status")
# → "fastapi_template:tenant-global:health:status:v1"
```

## Usage Patterns

### Pattern 1: Explicit Caching (Recommended for Complex Logic)

Use `cache_get`, `cache_set`, `cache_delete` for full control. Thread the
tenant explicitly on every call:

```python
from fastapi_template.cache import cache_get, cache_set, RedisDep
from fastapi_template.core.tenants import TenantDep
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_cached(
    session: AsyncSession,
    user_id: UUID,
    tenant: TenantDep,
    redis: RedisDep,
) -> User | None:
    """Get a user with the cache-aside pattern."""
    cached = await cache_get(redis, "user", str(user_id), User, tenant=tenant)
    if cached:
        return cached

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user:
        await cache_set(redis, "user", str(user_id), user, ttl=1800, tenant=tenant)

    return user
```

### Pattern 2: Decorator (Simple Cases)

Use the `@cached` decorator for automatic caching. It resolves **both** the
identifier and the tenant from the decorated function's own keyword arguments
(`id_param` / `tenant_param`) — no ambient context:

```python
from fastapi_template.cache import cached, RedisDep
from fastapi_template.core.tenants import TenantDep


@cached("user", tenant_param="tenant", id_param="user_id", ttl=1800, model_class=User)
async def get_user(
    session: AsyncSession,
    user_id: UUID,
    tenant: TenantDep,  # resolved for the cache key
    redis: RedisDep,    # required parameter
) -> User | None:
    """Get a user (automatically cached)."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

The `tenant_param` kwarg may hold a `TenantContext` (threaded as `tenant=`) or a
bare organization id (threaded as `organization_id=`). If either the id or the
tenant kwarg is missing, the decorator logs a warning and calls through
**uncached** — caching is a performance optimization, not a security boundary,
so it fails open at the decorator-ergonomics level.

### Pattern 3: Cache Invalidation on Updates

Always invalidate the cache when data changes, threading the same tenant used to
write it:

```python
from fastapi_template.cache import cache_delete


async def update_user(
    session: AsyncSession,
    user: User,
    payload: UserUpdate,
    tenant: TenantDep,
    redis: RedisDep,
) -> User:
    """Update a user and invalidate its cache entry."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    session.add(user)
    await session.flush()

    await cache_delete(redis, "user", str(user.id), tenant=tenant)

    return user
```

### Pattern 4: Batch Operations with Cache

Cache individual items during batch operations:

```python
async def get_users_batch(
    session: AsyncSession,
    user_ids: list[UUID],
    tenant: TenantDep,
    redis: RedisDep,
) -> list[User]:
    """Get multiple users with per-item caching."""
    users: list[User] = []
    uncached_ids: list[UUID] = []

    for user_id in user_ids:
        cached = await cache_get(redis, "user", str(user_id), User, tenant=tenant)
        if cached:
            users.append(cached)
        else:
            uncached_ids.append(user_id)

    if uncached_ids:
        result = await session.execute(select(User).where(User.id.in_(uncached_ids)))
        for user in result.scalars().all():
            await cache_set(redis, "user", str(user.id), user, tenant=tenant)
            users.append(user)

    return users
```

## Cache Key Format

Keys follow a hierarchical namespace:
`{prefix}:tenant-{tenant}:{resource}:{id}:{version}[:{suffix}]`

The literal segments are driven by module-level constants in
`fastapi_template/cache/keys.py` (`KEY_SEPARATOR`, `TENANT_PREFIX_FORMAT`,
`GLOBAL_TENANT_SENTINEL`, `DEFAULT_KEY_VERSION`) — never re-typed literals.

```python
# Basic tenant-scoped key
build_cache_key("user", user_id, organization_id=org_id)
# → "fastapi_template:tenant-<org>:user:<user_id>:v1"

# Global namespace (no tenant)
build_cache_key("health", "status")
# → "fastapi_template:tenant-global:health:status:v1"

# With a suffix for variations
build_cache_key("user", user_id, tenant=tenant, suffix="with_memberships")
# → "fastapi_template:tenant-<org>:user:<user_id>:v1:with_memberships"

# Version bump for schema changes
build_cache_key("user", user_id, tenant=tenant, version="v2")
# → "fastapi_template:tenant-<org>:user:<user_id>:v2"
```

The leading `prefix` is `CACHE_KEY_PREFIX` when set, otherwise the application
name (`app_name`).

## Cross-Service Cache Sharing

Services can share cache entries by using consistent key formats:

**Requirements for cross-service caching:**

1. Both services connect to the same Redis instance.
2. Both use the same `CACHE_KEY_PREFIX` (or explicitly construct matching keys).
3. Share Pydantic models for serialization consistency.
4. Coordinate cache invalidation across services.

## Metrics & Observability

### Prometheus Metrics

- `cache_hits_total{resource_type}` — total cache hits by resource type
- `cache_misses_total{resource_type}` — total cache misses by resource type
- `cache_operation_duration_seconds{operation}` — operation latency
  (`get`, `set`, `delete`)

### Example Queries

**Cache hit rate:**

```promql
sum(rate(cache_hits_total[5m])) /
sum(rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

**P95 cache latency:**

```promql
histogram_quantile(0.95, cache_operation_duration_seconds_bucket{operation="get"})
```

A deserialization failure or a Redis error is counted as a **miss** (never
raised), so the hit-rate metric also reflects degraded-cache conditions.

## Graceful Degradation

Every cache operation tolerates a `None` client and swallows Redis errors:

- `cache_get` → returns `None` (treated as a miss)
- `cache_set` → returns `False`
- `cache_delete` → returns `False`

This means callers can wrap reads/writes in caching unconditionally; when Redis
is unset or down, the application transparently falls back to its source of
truth (typically the database).

## Testing

### Unit Tests

Cache utilities are unit-tested with an `AsyncMock` standing in for the Redis
client (see `fastapi_template/tests/unit/cache/`). Because redis-py's client
methods are not `async def` at the class level, a plain `AsyncMock` (not
`spec=Redis`) is used so the awaited methods resolve correctly.

### Integration Tests

End-to-end tests run against real Docker Redis and are marked `integration`
(excluded from the default run). They reuse the shared `redis_url` fixture and
the Postgres-autouse opt-out pattern:

```bash
uv run pytest fastapi_template/tests/integration/test_cache_e2e.py -m integration
```
