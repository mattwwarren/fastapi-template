"""Tests for main.py's rate limiter storage backend selection."""

from __future__ import annotations

import logging

import pytest
from fastapi import Request
from limits.storage.memory import MemoryStorage
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from fastapi_template.core.config import settings
from fastapi_template.main import _rate_limit_storage_uri, limiter


class TestRateLimitStorageUri:
    def test_returns_none_when_redis_url_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("fastapi_template.main.settings.redis_url", None)

        result = _rate_limit_storage_uri()

        assert result is None

    def test_returns_redis_url_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("fastapi_template.main.settings.redis_url", "redis://user:pw@localhost:6379/0")

        result = _rate_limit_storage_uri()

        assert result == "redis://user:pw@localhost:6379/0"

    def test_warns_when_redis_url_unset(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr("fastapi_template.main.settings.redis_url", None)

        with caplog.at_level(logging.WARNING, logger="fastapi_template.main"):
            _rate_limit_storage_uri()

        assert any("REDIS_URL" in r.message for r in caplog.records)

    def test_logs_info_with_redacted_url_when_redis_url_set(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr("fastapi_template.main.settings.redis_url", "redis://user:pw@localhost:6379/0")

        with caplog.at_level(logging.INFO, logger="fastapi_template.main"):
            _rate_limit_storage_uri()

        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "localhost:6379/0" in messages
        assert "user:pw" not in messages  # credentials must never be logged


class TestLimiterWiring:
    def test_limiter_storage_uri_matches_helper(self) -> None:
        """Regression guard: the module-level Limiter must be wired from the
        helper, not a second hand-rolled expression (R3-style guard, mirrors
        test_client.py's test_wires_pool_timeout_into_blocking_pool)."""
        assert limiter._storage_uri == _rate_limit_storage_uri()

    def test_redis_timeout_and_in_memory_fallback_are_configured(self) -> None:
        assert limiter._storage_options == {
            "socket_connect_timeout": settings.redis_socket_connect_timeout,
            "socket_timeout": settings.redis_socket_timeout,
        }
        assert limiter._storage_options["socket_connect_timeout"] > 0
        assert limiter._storage_options["socket_timeout"] > 0
        assert limiter._in_memory_fallback_enabled is True
        assert len(limiter._in_memory_fallback) == 2

    def test_redis_outage_falls_back_to_in_memory_limits(self) -> None:
        class UnavailableStorage(MemoryStorage):
            def incr(self, key: str, expiry: int, amount: int = 1) -> int:
                raise ConnectionError

            def check(self) -> bool:
                return False

        def key_func(request: Request) -> str:
            return request.client.host if request.client else "client"

        def endpoint(_request: Request) -> None:
            return None

        outage_limiter = Limiter(
            key_func=key_func,
            default_limits=["1/minute"],
            storage_uri="redis://127.0.0.1:1/0",
            storage_options={"socket_connect_timeout": 0.01, "socket_timeout": 0.01},
            in_memory_fallback=["1/minute"],
            in_memory_fallback_enabled=True,
        )
        unavailable_storage = UnavailableStorage()
        outage_limiter._storage = unavailable_storage
        outage_limiter._limiter.storage = unavailable_storage
        scope = {
            "type": "http",
            "path": "/health",
            "method": "GET",
            "client": ("127.0.0.1", 1234),
            "headers": [],
        }

        outage_limiter._check_request_limit(Request(scope), endpoint)

        assert outage_limiter._storage_dead is True
        with pytest.raises(RateLimitExceeded):
            outage_limiter._check_request_limit(Request(scope), endpoint)
