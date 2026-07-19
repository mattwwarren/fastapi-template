"""Shared fixtures for cache unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


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
