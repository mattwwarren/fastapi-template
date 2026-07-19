"""Unit tests for cache client (connection factory + operations)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from pydantic import BaseModel

from fastapi_template.cache import client as cache_client
from fastapi_template.cache.client import (
    cache_delete,
    cache_get,
    cache_set,
    create_redis_client,
    get_redis,
)
from fastapi_template.core.metrics import (
    cache_hits_total,
    cache_misses_total,
)

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")


class _Sample(BaseModel):
    id: int
    name: str


def _hits(resource_type: str) -> float:
    return cache_hits_total.labels(resource_type=resource_type)._value.get()


def _misses(resource_type: str) -> float:
    return cache_misses_total.labels(resource_type=resource_type)._value.get()


# --------------------------------------------------------------------------- #
# create_redis_client
# --------------------------------------------------------------------------- #
class TestCreateRedisClient:
    async def test_returns_none_when_url_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("fastapi_template.cache.client.settings.redis_url", None)
        from_url = MagicMock()
        monkeypatch.setattr("fastapi_template.cache.client.ConnectionPool.from_url", from_url)

        result = await create_redis_client()

        assert result is None
        from_url.assert_not_called()

    async def test_returns_client_when_ping_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("fastapi_template.cache.client.settings.redis_url", "redis://user:pw@localhost:6379/0")
        monkeypatch.setattr("fastapi_template.cache.client.ConnectionPool.from_url", MagicMock(return_value="pool"))
        fake_client = AsyncMock()
        monkeypatch.setattr("fastapi_template.cache.client.Redis", MagicMock(return_value=fake_client))

        result = await create_redis_client()

        assert result is fake_client
        fake_client.ping.assert_awaited_once()

    async def test_returns_none_when_ping_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("fastapi_template.cache.client.settings.redis_url", "redis://localhost:6379/0")
        monkeypatch.setattr("fastapi_template.cache.client.ConnectionPool.from_url", MagicMock(return_value="pool"))
        fake_client = AsyncMock()
        fake_client.ping.side_effect = ConnectionError("boom")
        monkeypatch.setattr("fastapi_template.cache.client.Redis", MagicMock(return_value=fake_client))

        result = await create_redis_client()

        assert result is None


# --------------------------------------------------------------------------- #
# cache_get
# --------------------------------------------------------------------------- #
class TestCacheGet:
    async def test_none_client_returns_none(self) -> None:
        assert await cache_get(None, "user", "1") is None

    async def test_hit_returns_value_and_counts_hit(self, redis_mock: AsyncMock) -> None:
        redis_mock.get.return_value = '{"id": 1, "name": "alice"}'
        before = _hits("user")

        result = await cache_get(redis_mock, "user", "1", _Sample, organization_id=ORG_ID)

        assert result == _Sample(id=1, name="alice")
        assert _hits("user") == before + 1

    async def test_miss_returns_none_and_counts_miss(self, redis_mock: AsyncMock) -> None:
        redis_mock.get.return_value = None
        before = _misses("user")

        result = await cache_get(redis_mock, "user", "1", _Sample)

        assert result is None
        assert _misses("user") == before + 1

    async def test_redis_error_returns_none_counts_miss(self, redis_mock: AsyncMock) -> None:
        redis_mock.get.side_effect = ConnectionError("down")
        before = _misses("user")

        result = await cache_get(redis_mock, "user", "1", _Sample)

        assert result is None
        assert _misses("user") == before + 1

    async def test_serialization_error_counts_miss(self, redis_mock: AsyncMock) -> None:
        redis_mock.get.return_value = "{not-json"
        before = _misses("user")

        result = await cache_get(redis_mock, "user", "1", _Sample)

        assert result is None
        assert _misses("user") == before + 1


# --------------------------------------------------------------------------- #
# cache_set
# --------------------------------------------------------------------------- #
class TestCacheSet:
    async def test_none_client_returns_false(self) -> None:
        assert await cache_set(None, "user", "1", _Sample(id=1, name="a")) is False

    async def test_uses_default_ttl_when_none(self, redis_mock: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("fastapi_template.cache.client.settings.redis_default_ttl", 3600)

        result = await cache_set(redis_mock, "user", "1", _Sample(id=1, name="a"))

        assert result is True
        _key, ttl, _data = redis_mock.setex.call_args.args
        assert ttl == 3600

    async def test_explicit_ttl_overrides_default(self, redis_mock: AsyncMock) -> None:
        result = await cache_set(redis_mock, "user", "1", _Sample(id=1, name="a"), ttl=99)

        assert result is True
        _key, ttl, _data = redis_mock.setex.call_args.args
        assert ttl == 99

    async def test_setex_error_returns_false(self, redis_mock: AsyncMock) -> None:
        redis_mock.setex.side_effect = ConnectionError("down")

        result = await cache_set(redis_mock, "user", "1", _Sample(id=1, name="a"))

        assert result is False


# --------------------------------------------------------------------------- #
# cache_delete
# --------------------------------------------------------------------------- #
class TestCacheDelete:
    async def test_none_client_returns_false(self) -> None:
        assert await cache_delete(None, "user", "1") is False

    async def test_success_returns_true(self, redis_mock: AsyncMock) -> None:
        result = await cache_delete(redis_mock, "user", "1", organization_id=ORG_ID)

        assert result is True
        redis_mock.delete.assert_awaited_once()

    async def test_delete_error_returns_false(self, redis_mock: AsyncMock) -> None:
        redis_mock.delete.side_effect = ConnectionError("down")

        result = await cache_delete(redis_mock, "user", "1")

        assert result is False


# --------------------------------------------------------------------------- #
# get_redis / RedisDep
# --------------------------------------------------------------------------- #
class TestGetRedis:
    async def test_yields_module_global(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sentinel = AsyncMock()
        monkeypatch.setattr(cache_client, "redis_client", sentinel)

        gen = get_redis()
        yielded = await gen.__anext__()

        assert yielded is sentinel

    async def test_yields_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(cache_client, "redis_client", None)

        gen = get_redis()
        yielded = await gen.__anext__()

        assert yielded is None
