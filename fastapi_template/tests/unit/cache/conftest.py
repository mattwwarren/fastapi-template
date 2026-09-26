"""Shared fixtures for cache unit tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest

from fastapi_template.cache import client as cache_client


@pytest.fixture(autouse=True)
def _reset_redis_client_global() -> Generator[None]:
    """Reset the module-level redis_client global between tests.

    Mirrors tests/unit/test_realtime.py's _reset_sio() convention: some tests
    call create_redis_client() directly, which mutates this global as a
    documented side effect outside of monkeypatch's auto-restore.
    """
    cache_client.redis_client = None
    yield
    cache_client.redis_client = None


@pytest.fixture
def redis_mock() -> AsyncMock:
    """Loose AsyncMock standing in for a redis.asyncio.Redis client.

    A plain AsyncMock is used (not ``spec=Redis``) because redis-py's client
    methods are not ``async def`` at the class level, so ``spec`` would make
    ``get``/``setex``/``delete`` synchronous child mocks that cannot be
    awaited. Every accessed attribute (``get``, ``setex``, ``delete``,
    ``ping``, ``aclose``) is therefore an awaitable AsyncMock that individual
    tests configure with return values / side effects.
    """
    return AsyncMock()
