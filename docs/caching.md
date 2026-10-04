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

The examples below cache a small `UserSummary` projection rather than the `User`
row itself: `User` carries `email` and is marked `pii=True`, so `cache_set`
refuses it (see [Data Classification & PII](#data-classification--pii)).

```python
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_template.cache import cache_get, cache_set, RedisDep
from fastapi_template.core.tenants import TenantDep


class UserSummary(BaseModel):
    """Non-PII projection of User -- the cacheable shape (no email)."""

    id: UUID
    name: str


async def get_user_cached(
    session: AsyncSession,
    user_id: UUID,
    tenant: TenantDep,
    redis: RedisDep,
) -> UserSummary | None:
    """Get a user summary with the cache-aside pattern."""
    cached = await cache_get(redis, "user", str(user_id), UserSummary, tenant=tenant)
    if cached:
        return cached

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None

    summary = UserSummary(id=user.id, name=user.name)
    await cache_set(redis, "user", str(user_id), summary, ttl=1800, tenant=tenant)

    return summary
```

### Pattern 2: Decorator (Simple Cases)

Use the `@cached` decorator for automatic caching. It resolves **both** the
identifier and the tenant from the decorated function's own keyword arguments
(`id_param` / `tenant_param`) — no ambient context:

```python
from fastapi_template.cache import cached, RedisDep
from fastapi_template.core.tenants import TenantDep


@cached("user", tenant_param="tenant", id_param="user_id", ttl=1800, model_class=UserSummary)
async def get_user(
    session: AsyncSession,
    *,                  # id/tenant/redis MUST be keyword-only
    user_id: UUID,
    tenant: TenantDep,  # resolved for the cache key
    redis: RedisDep,    # required parameter
) -> UserSummary | None:
    """Get a user summary (automatically cached; UserSummary from Pattern 1)."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return UserSummary(id=user.id, name=user.name) if user else None
```

The `tenant_param` kwarg may hold a `TenantContext` (threaded as `tenant=`) or a
bare organization id (threaded as `organization_id=`). If either the id or the
tenant kwarg is missing, the decorator logs a warning and calls through
**uncached** — caching is a performance optimization, not a security boundary,
so it fails open at the decorator-ergonomics level.

Because the decorator reads these values from keyword arguments only, a
positional call would silently bypass the cache. To prevent that, `id_param`,
`tenant_param` and `redis` — when present in the signature — must be declared
**keyword-only** (after a bare `*`). Decorating a function that declares any of
them as positional-or-keyword raises `TypeError` at import time.

### Pattern 3: Cache Invalidation on Updates

Always invalidate the cache when data changes, threading the same tenant used to
write it. (Here `user: User` is the ORM row being persisted, not a cache payload;
`cache_delete` never serializes a model, so the `pii=True` guard does not apply.)

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

Cache individual items during batch operations (again caching the non-PII
`UserSummary` projection from Pattern 1):

```python
async def get_users_batch(
    session: AsyncSession,
    user_ids: list[UUID],
    tenant: TenantDep,
    redis: RedisDep,
) -> list[UserSummary]:
    """Get multiple user summaries with per-item caching."""
    summaries: list[UserSummary] = []
    uncached_ids: list[UUID] = []

    for user_id in user_ids:
        cached = await cache_get(redis, "user", str(user_id), UserSummary, tenant=tenant)
        if cached:
            summaries.append(cached)
        else:
            uncached_ids.append(user_id)

    if uncached_ids:
        result = await session.execute(select(User).where(User.id.in_(uncached_ids)))
        for user in result.scalars().all():
            summary = UserSummary(id=user.id, name=user.name)
            await cache_set(redis, "user", str(user.id), summary, tenant=tenant)
            summaries.append(summary)

    return summaries
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
- `cache_misses_total{resource_type}` — total genuine cache misses (key absent)
  by resource type
- `cache_errors_total{resource_type, operation}` — total Redis backend or
  deserialization failures by resource type and operation (`get`, `set`,
  `delete`)
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

**Cache error rate by operation:**

```promql
sum by (operation) (rate(cache_errors_total[5m]))
```

Errors are never raised to the caller, but they are **not** counted as misses:
a genuine miss (key absent) increments `cache_misses_total`, while a Redis
error or a deserialization failure increments `cache_errors_total`. The hit
rate therefore measures cache effectiveness, and a degraded backend shows up
separately in the error rate instead of silently depressing the hit rate.

## Graceful Degradation

Every cache operation tolerates a `None` client and swallows Redis errors:

- `cache_get` → returns `None` (the caller falls back as on a miss)
- `cache_set` → returns `False`
- `cache_delete` → returns `False`

This means callers can wrap reads/writes in caching unconditionally; when Redis
is unset or down, the application transparently falls back to its source of
truth (typically the database).

The one deliberate exception is `CachePiiViolationError`: it signals a
programming error, not degraded infrastructure, so `cache_set` raises it rather
than returning `False` (see below).

## Data Classification & PII

Caching is **not** a data-classification boundary (see ARCHITECTURE.md,
Invariant 10). `@cached` and `cache_set` serialize a model to plaintext JSON in
Redis, so every field on the cached model — including any PII or other
sensitive personal data — lands in Redis as-is. Adding caching to a model does
not change what protections its sensitive fields need.

This is **enforced in code** by a model-level marker. A model class that carries
PII declares `pii: ClassVar[bool] = True`:

```python
from typing import ClassVar

from pydantic import BaseModel


class SsnRecord(BaseModel):
    pii: ClassVar[bool] = True

    ssn: str
```

`cache_set` — and therefore `@cached`, which writes through it — raises
`CachePiiViolationError` (from `fastapi_template.cache`) for any such model,
before Redis is ever touched. The marker is a `ClassVar`, so it is not a
Pydantic field or a database column. It is opt-in and defaults to `False` for
unmarked models. In the template, `User`, `UserRead`, `UserInfo`, and
`CurrentUser` are marked, because each carries `email`.

**Known behavior:**

- The exception **propagates** out of `cache_set` and out of the
  `@cached`-decorated function. It is not swallowed into a `False` return or
  counted in `cache_errors_total`. An endpoint that caches a marked model
  therefore returns a 500 on its first write-path request unless the caller
  catches `CachePiiViolationError` — deliberately, so the mistake fails loudly
  in tests and at runtime.
- The check fires **even with Redis disabled** (`redis is None`), so the
  mistake surfaces in development rather than only in a Redis-enabled
  deployment.
- The marker is checked on the **top-level cached object only**. A non-marked
  container that nests a marked model (e.g. `OrganizationRead.users:
  list[UserInfo]`) is **not** caught — mark such containers yourself.

For anything not marked, apply this rule of thumb:

- **Don't cache raw PII-bearing models.** If a model carries sensitive fields,
  either apply the same at-rest controls in Redis that the data needs in
  Postgres, or keep it out of the cache entirely.
- **Cache a derived or redacted projection instead.** Define a narrower
  Pydantic model containing only the non-sensitive fields the hot path needs,
  and cache that.
- **Treat the cache TTL as retention.** Cached copies persist until expiry or
  invalidation — factor that into any data-retention or erasure obligations.

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

`test_cache_lifespan_integration.py` additionally runs a probe app through the
real application lifespan to prove `RedisDep` resolves a live client inside an
actual request (and `None` when `REDIS_URL` is unset or after shutdown).
