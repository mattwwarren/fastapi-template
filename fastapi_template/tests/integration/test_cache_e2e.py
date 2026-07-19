"""End-to-end integration tests for the Redis cache layer.

Exercises the real cache stack (connection factory, key building, serialization,
operations, decorator) against a live Docker Redis, reusing the shared
``redis_url`` fixture. Marked ``integration`` so the default suite skips it.

Requires Docker Redis (started by tests/docker-compose.yml).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel
from redis.asyncio import Redis

from fastapi_template.cache.client import cache_delete, cache_get, cache_set, create_redis_client
from fastapi_template.cache.decorator import cached
from fastapi_template.cache.keys import build_cache_key
from fastapi_template.core.tenants import TenantContext
from fastapi_template.models.membership import MembershipRole

pytestmark = pytest.mark.integration

USER_ID = UUID("22222222-2222-2222-2222-222222222222")


# Override autouse fixtures that depend on Postgres -- cache tests only need Redis.
@pytest.fixture(autouse=True)
def reset_db() -> None:
    """No-op: cache tests don't use the database."""


@pytest.fixture(autouse=True)
async def default_auth_user_in_org() -> None:
    """No-op: cache tests don't use the database."""


class Widget(BaseModel):
    id: int
    name: str


def _tenant(org_id: UUID) -> TenantContext:
    return TenantContext(organization_id=org_id, user_id=USER_ID, role=MembershipRole.MEMBER)


@pytest.fixture
async def cache_redis(redis_url: str, monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[Redis]:
    """Real Redis client built via create_redis_client against Docker Redis."""
    monkeypatch.setattr("fastapi_template.cache.client.settings.redis_url", redis_url)
    client = await create_redis_client()
    assert client is not None
    await client.flushdb()
    yield client
    await client.aclose()


async def test_set_get_round_trip(cache_redis: Redis) -> None:
    org_id = uuid4()
    widget = Widget(id=1, name="alpha")

    assert await cache_set(cache_redis, "widget", "1", widget, organization_id=org_id) is True
    result = await cache_get(cache_redis, "widget", "1", Widget, organization_id=org_id)

    assert result == widget


async def test_ttl_is_applied(cache_redis: Redis) -> None:
    org_id = uuid4()
    await cache_set(cache_redis, "widget", "1", Widget(id=1, name="a"), ttl=60, organization_id=org_id)

    key = build_cache_key("widget", "1", organization_id=org_id)
    ttl = await cache_redis.ttl(key)

    assert 0 < ttl <= 60


async def test_ttl_expiry_evicts_value(cache_redis: Redis) -> None:
    org_id = uuid4()
    await cache_set(cache_redis, "widget", "1", Widget(id=1, name="a"), ttl=1, organization_id=org_id)

    await asyncio.sleep(1.2)

    result = await cache_get(cache_redis, "widget", "1", Widget, organization_id=org_id)
    assert result is None


async def test_delete_removes_key(cache_redis: Redis) -> None:
    org_id = uuid4()
    await cache_set(cache_redis, "widget", "1", Widget(id=1, name="a"), organization_id=org_id)

    assert await cache_delete(cache_redis, "widget", "1", organization_id=org_id) is True
    assert await cache_get(cache_redis, "widget", "1", Widget, organization_id=org_id) is None


async def test_tenant_isolation_no_cross_contamination(cache_redis: Redis) -> None:
    org_a = uuid4()
    org_b = uuid4()
    tenant_a = _tenant(org_a)
    tenant_b = _tenant(org_b)

    await cache_set(cache_redis, "widget", "1", Widget(id=1, name="a-value"), tenant=tenant_a)
    await cache_set(cache_redis, "widget", "1", Widget(id=1, name="b-value"), tenant=tenant_b)

    result_a = await cache_get(cache_redis, "widget", "1", Widget, tenant=tenant_a)
    result_b = await cache_get(cache_redis, "widget", "1", Widget, tenant=tenant_b)

    assert isinstance(result_a, Widget)
    assert isinstance(result_b, Widget)
    assert result_a.name == "a-value"
    assert result_b.name == "b-value"
    assert build_cache_key("widget", "1", tenant=tenant_a) != build_cache_key("widget", "1", tenant=tenant_b)


async def test_decorator_end_to_end(cache_redis: Redis) -> None:
    org_id = uuid4()
    calls: list[int] = []

    @cached("widget", tenant_param="tenant", id_param="widget_id", model_class=Widget)
    async def get_widget(*, tenant: TenantContext, widget_id: str, redis: Redis) -> Widget:  # noqa: ARG001
        calls.append(1)
        return Widget(id=int(widget_id), name="fetched")

    tenant = _tenant(org_id)

    first = await get_widget(tenant=tenant, widget_id="5", redis=cache_redis)
    second = await get_widget(tenant=tenant, widget_id="5", redis=cache_redis)

    assert first == second == Widget(id=5, name="fetched")
    assert calls == [1]  # second call served from cache


async def test_graceful_degradation_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Point at a closed port so connection fails during create_redis_client.
    monkeypatch.setattr("fastapi_template.cache.client.settings.redis_url", "redis://127.0.0.1:1/0")

    client = await create_redis_client()

    assert client is None
    # Downstream operations must be silent no-ops, never raise.
    assert await cache_get(client, "widget", "1", Widget) is None
    assert await cache_set(client, "widget", "1", Widget(id=1, name="a")) is False
    assert await cache_delete(client, "widget", "1") is False
