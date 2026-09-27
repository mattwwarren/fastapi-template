"""Tests for main.py's rate limiter storage backend selection."""

from __future__ import annotations

import logging

import pytest

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
