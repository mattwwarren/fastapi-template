"""Shared fixtures for cache unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from redis.asyncio import Redis


@pytest.fixture
def redis_mock() -> AsyncMock:
    """AsyncMock loosely spec'd to redis.asyncio.Redis.

    Exposes the async methods the cache layer calls (``get``, ``setex``,
    ``delete``, ``ping``, ``aclose``). Individual tests configure return
    values / side effects as needed.
    """
    mock = AsyncMock(spec=Redis)
    return mock
