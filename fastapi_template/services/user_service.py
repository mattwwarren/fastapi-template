"""User data access helpers for services and endpoints.

Metrics Usage Examples:
    This module demonstrates comprehensive Prometheus metrics integration:

    - Counters: users_created_total tracks total user creations
    - Histograms: database_query_duration_seconds tracks query performance
    - Gauges: Could track active_users_count (not implemented here)

    Metrics are recorded AFTER successful operations to ensure accuracy.
    Labels are used consistently (environment from settings.environment).
"""

import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fastapi_template.core.config import settings
from fastapi_template.core.metrics import (
    database_query_duration_seconds,
    users_created_total,
)
from fastapi_template.models.membership import Membership
from fastapi_template.models.organization import Organization
from fastapi_template.models.user import User, UserCreate, UserUpdate

# Optional: Import cache utilities for cached variant
try:
    from fastapi_template.cache import cache_delete, cache_get, cache_set

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    """Fetch a single user by ID.

    Demonstrates histogram metric usage for tracking database query duration.
    Uses time.perf_counter() for high-precision timing.

    Example metric output:
        database_query_duration_seconds{query_type="select"} 0.0023
    """
    # Record timing for database query using histogram
    start = time.perf_counter()
    result = await session.execute(select(User).where(col(User.id) == user_id))
    duration = time.perf_counter() - start

    # Observe duration in histogram with query_type label
    database_query_duration_seconds.labels(query_type="select").observe(duration)

    return result.scalar_one_or_none()


async def get_user_cached(session: AsyncSession, user_id: UUID, redis: object = None) -> User | None:
    """Fetch a single user by ID with Redis caching (cache-aside pattern).

    This is an example of explicit caching for read-heavy operations.
    Use this variant for endpoints with high traffic to reduce database load.

    Cache behavior:
    - Cache hit: Returns user from Redis (1-3ms)
    - Cache miss: Queries database and populates cache (10-50ms)
    - Redis unavailable: Falls back to database (graceful degradation)

    Args:
        session: Database session
        user_id: User UUID
        redis: Optional Redis client (None if caching disabled)

    Returns:
        User if found, None otherwise

    Example usage in endpoint:
        from fastapi_template.core.cache import RedisDep

        @router.get("/{user_id}")
        async def get_user_endpoint(
            user_id: UUID,
            session: SessionDep,
            redis: RedisDep,
        ) -> UserRead:
            user = await get_user_cached(session, user_id, redis)
            if not user:
                raise HTTPException(status_code=404)
            return UserRead.model_validate(user)

    Metrics:
        - cache_hits_total{resource_type="user"}: Cache hits
        - cache_misses_total{resource_type="user"}: Cache misses
        - database_query_duration_seconds{query_type="select"}: DB query time
    """
    if not CACHE_AVAILABLE or redis is None:
        # Cache not available - fall back to database
        return await get_user(session, user_id)

    # Try cache first (cache-aside pattern)
    cached = await cache_get(redis, "user", str(user_id), User)
    if cached:
        return cached

    # Cache miss - query database with timing
    start = time.perf_counter()
    result = await session.execute(select(User).where(col(User.id) == user_id))
    duration = time.perf_counter() - start

    # Record database query duration
    database_query_duration_seconds.labels(query_type="select").observe(duration)

    user = result.scalar_one_or_none()

    # Populate cache for next request (30 minute TTL)
    if user:
        await cache_set(redis, "user", str(user_id), user, ttl=1800)

    return user


async def list_users(session: AsyncSession, offset: int = 0, limit: int = 100) -> list[User]:
    result = await session.execute(select(User).offset(offset).limit(limit))
    return list(result.scalars().all())


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    """Create a new user.

    Demonstrates counter metric usage for tracking user creation events.
    Counter is incremented AFTER successful commit to ensure accuracy.

    Example metric output:
        users_created_total{environment="production"} 1234
        users_created_total{environment="staging"} 56

    Note:
        Metrics are recorded after successful operations only. If commit fails,
        the counter is not incremented, maintaining accurate totals.
    """
    user = User(**payload.model_dump())
    session.add(user)
    await session.flush()  # type: ignore[attr-defined]
    await session.refresh(user)

    # Increment counter AFTER successful creation
    # Label with environment to track metrics per deployment environment
    users_created_total.labels(environment=settings.environment).inc()

    return user


async def update_user(session: AsyncSession, user: User, payload: UserUpdate, redis: object = None) -> User:
    """Update user and invalidate cache.

    Demonstrates cache invalidation pattern to prevent stale reads.
    Always invalidate cache when updating data to maintain consistency.

    Args:
        session: Database session
        user: User instance to update
        payload: Update payload
        redis: Optional Redis client for cache invalidation

    Returns:
        Updated user instance
    """
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)
    session.add(user)
    await session.flush()  # type: ignore[attr-defined]
    await session.refresh(user)

    # Invalidate cache to prevent stale reads
    if CACHE_AVAILABLE and redis:
        await cache_delete(redis, "user", str(user.id))

    return user


async def delete_user(session: AsyncSession, user: User, redis: object = None) -> None:
    """Delete user and invalidate cache.

    Args:
        session: Database session
        user: User instance to delete
        redis: Optional Redis client for cache invalidation
    """
    user_id = user.id  # Capture before delete
    await session.delete(user)
    await session.flush()  # type: ignore[attr-defined]

    # Invalidate cache after deletion
    if CACHE_AVAILABLE and redis:
        await cache_delete(redis, "user", str(user_id))


async def list_organizations_for_user(session: AsyncSession, user_id: UUID) -> list[Organization]:
    result = await session.execute(
        select(Organization)
        .join(
            Membership,
            col(Membership.organization_id) == col(Organization.id),
        )
        .where(col(Membership.user_id) == user_id)
    )
    return list(result.scalars().all())


async def list_organizations_for_users(session: AsyncSession, user_ids: list[UUID]) -> dict[UUID, list[Organization]]:
    if not user_ids:
        return {}
    result = await session.execute(
        select(Membership.user_id, Organization)
        .join(
            Membership,
            col(Membership.organization_id) == col(Organization.id),
        )
        .where(col(Membership.user_id).in_(user_ids))
    )
    mapping: dict[UUID, list[Organization]] = {user_id: [] for user_id in user_ids}
    for user_id, organization in result.all():
        if user_id in mapping:
            mapping[user_id].append(organization)
    return mapping
