# Redis Caching Guide

Complete guide to using Redis caching in this FastAPI template.

## Overview

This template provides optional Redis caching with:
- **Cache-aside pattern** for read-heavy endpoints
- **Multi-tenant isolation** via cache key namespacing
- **Cross-service compatibility** via JSON serialization
- **Graceful degradation** if Redis unavailable
- **Observability** via Prometheus metrics

## Configuration

See [CONFIGURATION-GUIDE.md](../CONFIGURATION-GUIDE.md#redis-caching-configuration) for environment variables.

## Usage Patterns

### Pattern 1: Explicit Caching (Recommended for Complex Logic)

Use `cache_get`, `cache_set`, `cache_delete` utilities for full control:

```python
from fastapi_template.cache import cache_get, cache_set, cache_delete
from fastapi_template.core.cache import RedisDep
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_cached(
    session: AsyncSession,
    user_id: UUID,
    redis: RedisDep,
) -> User | None:
    """Get user with cache-aside pattern."""
    # Try cache first
    cached = await cache_get(redis, "user", str(user_id), User)
    if cached:
        return cached

    # Cache miss - query database
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    # Populate cache for next request
    if user:
        await cache_set(redis, "user", str(user_id), user, ttl=1800)  # 30 min

    return user
```

### Pattern 2: Decorator (Simple Cases)

Use `@cached` decorator for automatic caching:

```python
from fastapi_template.cache import cached
from fastapi_template.core.cache import RedisDep

@cached("user", id_param="user_id", ttl=1800, model_class=User)
async def get_user(
    session: AsyncSession,
    user_id: UUID,
    redis: RedisDep,  # Required parameter
) -> User | None:
    """Get user (automatically cached)."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

### Pattern 3: Cache Invalidation on Updates

Always invalidate cache when data changes:

```python
from fastapi_template.cache import cache_delete

async def update_user(
    session: AsyncSession,
    user: User,
    payload: UserUpdate,
    redis: RedisDep,
) -> User:
    """Update user and invalidate cache."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    session.add(user)
    await session.flush()

    # Invalidate cache (prevents stale reads)
    await cache_delete(redis, "user", str(user.id))

    return user
```

### Pattern 4: Batch Operations with Cache

Cache individual items during batch operations:

```python
async def get_users_batch(
    session: AsyncSession,
    user_ids: list[UUID],
    redis: RedisDep,
) -> list[User]:
    """Get multiple users with intelligent caching."""
    users = []
    uncached_ids = []

    # Try cache for each ID
    for user_id in user_ids:
        cached = await cache_get(redis, "user", str(user_id), User)
        if cached:
            users.append(cached)
        else:
            uncached_ids.append(user_id)

    # Fetch uncached users from database
    if uncached_ids:
        result = await session.execute(
            select(User).where(User.id.in_(uncached_ids))
        )
        db_users = result.scalars().all()

        # Cache newly fetched users
        for user in db_users:
            await cache_set(redis, "user", str(user.id), user)
            users.append(user)

    return users
```

## Cache Key Format

Keys follow hierarchical namespace: `{prefix}:{tenant}:{resource}:{id}:{version}:{suffix}`

**Examples:**
```python
# Basic key
build_cache_key("user", user_id)
# → "fastapi_template:tenant-global:user:uuid-456:v1"

# Multi-tenant key (auto-detected from request context)
build_cache_key("user", user_id)  # When ENFORCE_TENANT_ISOLATION=true
# → "fastapi_template:tenant-org-123:user:uuid-456:v1"

# Explicit tenant
build_cache_key("organization", org_id, tenant_id=org_id)
# → "fastapi_template:tenant-org-789:organization:uuid-012:v1"

# With suffix for variations
build_cache_key("user", user_id, suffix="with_memberships")
# → "fastapi_template:tenant-global:user:uuid-456:v1:with_memberships"

# Version for schema changes
build_cache_key("user", user_id, version="v2")
# → "fastapi_template:tenant-global:user:uuid-456:v2"
```

## Multi-Tenancy

Cache keys automatically include tenant ID from request context when `ENFORCE_TENANT_ISOLATION=true`:

```python
# Tenant auto-detected from request context
build_cache_key("user", user_id)
# → "fastapi_template:tenant-org-123:user:uuid-456:v1"

# Explicit global cache (health checks, system data)
build_cache_key("health", "status", tenant_id="global")
# → "fastapi_template:tenant-global:health:status:v1"

# If tenant isolation enforced but no tenant context → ValueError
# This prevents cross-tenant cache leaks
```

**Security Note**: When `ENFORCE_TENANT_ISOLATION=true`, cache operations **require** tenant context. Missing tenant ID raises `ValueError` to prevent accidental cache leaks.

## Cross-Service Cache Sharing

Services can share cache by using consistent key formats:

**Service A (fastapi-template) writes**:
```python
await cache_set(redis, "user", user_id, user_obj, ttl=3600)
# Key: "fastapi_template:tenant-org-123:user:uuid-456:v1"
```

**Service B (consumer-service) reads**:
```python
# Use same key format
cached_user = await cache_get(redis, "user", user_id, User)
# Key: "fastapi_template:tenant-org-123:user:uuid-456:v1"
```

**Requirements for cross-service caching:**
1. Both services connect to same Redis instance
2. Use same `CACHE_KEY_PREFIX` (or explicitly construct matching keys)
3. Share Pydantic models for serialization consistency
4. Coordinate cache invalidation across services

## Metrics & Observability

### Prometheus Metrics

**Available metrics:**
- `cache_hits_total{resource_type}` - Total cache hits by resource type
- `cache_misses_total{resource_type}` - Total cache misses by resource type
- `cache_operation_duration_seconds{operation}` - Operation latency (get, set, delete)

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

**Cache hit rate by resource type:**
```promql
sum by(resource_type) (rate(cache_hits_total[5m])) /
sum by(resource_type) (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

### Structured Logging

Cache operations include request context:

```json
{
  "operation": "cache_get",
  "resource_type": "user",
  "cache_hit": true,
  "duration_ms": 2.3,
  "request_id": "req-123",
  "org_id": "org-456"
}
```

## Testing

### Unit Tests

Test cache utilities in isolation:

```python
from fastapi_template.cache import cache_get, cache_set
from redis.asyncio import Redis

async def test_cache_get_hit(redis_client: Redis):
    """Test cache hit returns cached value."""
    # Arrange
    await redis_client.set("test-key", json.dumps({"id": 1}))

    # Act
    result = await cache_get(redis_client, "test", "key")

    # Assert
    assert result == {"id": 1}


async def test_cache_get_miss(redis_client: Redis):
    """Test cache miss returns None."""
    result = await cache_get(redis_client, "test", "nonexistent")
    assert result is None
```

### Integration Tests

Test cached endpoints end-to-end:

```python
async def test_cached_user_endpoint(client: AsyncClient, redis_client: Redis):
    """Test user endpoint uses cache."""
    # First request (cache miss)
    response1 = await client.get(f"/users/{user_id}")
    assert response1.status_code == 200

    # Verify cache populated
    cache_key = f"fastapi_template:tenant-global:user:{user_id}:v1"
    assert await redis_client.exists(cache_key)

    # Second request (cache hit)
    response2 = await client.get(f"/users/{user_id}")
    assert response2.status_code == 200
    assert response2.json() == response1.json()
```

## Best Practices

### ✅ DO

- **Use caching for read-heavy endpoints** (GET requests with high traffic)
- **Invalidate cache on writes** (UPDATE, DELETE operations)
- **Set appropriate TTLs** based on data volatility (see TTL recommendations)
- **Include tenant ID** in multi-tenant applications for isolation
- **Use JSON serialization** for cross-service compatibility
- **Monitor cache hit rates** and latency via Prometheus
- **Handle Redis unavailability** gracefully (built-in with this implementation)
- **Use explicit cache keys** for predictable behavior
- **Version cache keys** when schema changes (`version="v2"`)

### ❌ DON'T

- **Don't cache sensitive data** without encryption (PII, credentials, tokens)
- **Don't use long TTLs** for frequently changing data (leads to stale reads)
- **Don't forget to invalidate** on updates (causes data inconsistency)
- **Don't use pickle** serialization (security risk, not cross-service compatible)
- **Don't assume Redis is always available** (use graceful degradation)
- **Don't cache large objects** (>1MB) without compression
- **Don't cache non-deterministic results** (random data, timestamps)
- **Don't bypass tenant isolation** in multi-tenant apps (security risk)

## Troubleshooting

### Redis Connection Failures

**Symptoms**: Application logs "Redis caching disabled" and continues without cache

```
WARNING: Failed to connect to Redis: ConnectionError. Caching disabled.
```

**Solutions:**
1. Check `REDIS_URL` is correct and Redis is running
2. Verify network connectivity to Redis host
3. Check Redis authentication credentials
4. Inspect Redis logs for errors

### Low Cache Hit Rate

**Symptoms**: Metrics show hit rate < 50%

**Common causes:**
- TTL too short (data expires before reuse)
- Cache eviction due to memory pressure
- Inconsistent key generation
- Cache invalidation too aggressive

**Solutions:**
1. Increase Redis memory (`maxmemory` config)
2. Adjust eviction policy (`maxmemory-policy allkeys-lru`)
3. Increase TTLs for stable data
4. Audit cache key generation logic
5. Review invalidation patterns

### Cache Misses Despite Expected Hits

**Symptoms**: Cache key lookups return None unexpectedly

**Debug steps:**
```python
# Log cache keys for debugging
logger.info(f"Cache key: {build_cache_key('user', user_id)}")
```

**Common issues:**
- Tenant ID mismatch (check `get_org_id()` output)
- Version mismatch (v1 vs v2 keys)
- Key prefix inconsistency (`CACHE_KEY_PREFIX` differs)
- Cache was invalidated unexpectedly

### Performance Degradation

**Symptoms**: Slow response times despite caching

**Check:**
1. **Cache latency**: P95 > 10ms indicates Redis performance issues
2. **Connection pool**: Exhaustion causes blocking (increase `REDIS_POOL_SIZE`)
3. **Network latency**: Redis on different network/region
4. **Serialization cost**: Large objects take time to serialize/deserialize

**Solutions:**
- Scale Redis vertically (more CPU/memory)
- Use Redis Cluster for horizontal scaling
- Place Redis in same network/region as app
- Implement compression for large cached objects

## Advanced Topics

### Cache Warming

Pre-populate cache with frequently accessed data:

```python
async def warm_cache_on_startup(redis: Redis, session: AsyncSession):
    """Warm cache with hot data during startup."""
    # Fetch top 100 most accessed users
    result = await session.execute(
        select(User).order_by(User.last_login_at.desc()).limit(100)
    )
    users = result.scalars().all()

    # Pre-populate cache
    for user in users:
        await cache_set(redis, "user", str(user.id), user, ttl=7200)
```

### Conditional Caching

Cache based on request headers or parameters:

```python
async def get_user_conditional(
    user_id: UUID,
    use_cache: bool = True,  # Query parameter
    session: AsyncSession,
    redis: RedisDep,
) -> User:
    """Get user with optional cache bypass."""
    if use_cache:
        cached = await cache_get(redis, "user", str(user_id), User)
        if cached:
            return cached

    # Database fetch...
```

### Cache Stampede Prevention

Prevent thundering herd on cache miss:

```python
import asyncio
from contextlib import asynccontextmanager

# In-memory lock per cache key (app-local)
_locks: dict[str, asyncio.Lock] = {}

@asynccontextmanager
async def cache_lock(key: str):
    """Acquire lock for cache key to prevent stampede."""
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    async with _locks[key]:
        yield

async def get_user_with_stampede_prevention(
    user_id: UUID,
    session: AsyncSession,
    redis: RedisDep,
) -> User:
    """Get user with cache stampede prevention."""
    key = build_cache_key("user", str(user_id))

    # Try cache
    cached = await cache_get(redis, "user", str(user_id), User)
    if cached:
        return cached

    # Use lock to prevent multiple simultaneous DB queries
    async with cache_lock(key):
        # Double-check cache (another request may have populated it)
        cached = await cache_get(redis, "user", str(user_id), User)
        if cached:
            return cached

        # Fetch from DB and cache
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            await cache_set(redis, "user", str(user_id), user)
        return user
```

## Further Reading

- [Redis Best Practices](https://redis.io/docs/manual/patterns/)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Prometheus Metrics](https://prometheus.io/docs/practices/naming/)
- [Cache-Aside Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside)
