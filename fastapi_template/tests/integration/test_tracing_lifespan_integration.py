"""Integration tests for the disabled OpenTelemetry tracing path in the lifespan.

Proves that with tracing disabled (explicitly or by default) the real
``main.lifespan`` starts, serves a request, and shuts down without touching
the optional ``otel`` extra, leaving ``app.state.tracer_provider`` as ``None``.

The assertions are on ``app.state`` rather than ``sys.modules``: the ``otel``
extra is installed for the whole integration job, and xdist collection may
import ``opentelemetry`` via neighbouring test modules before this one runs.

A throwaway ``FastAPI(lifespan=lifespan)`` probe app is used rather than the
production ``app`` singleton so the probe route never leaks into other tests.

Requires Docker Postgres (started by tests/docker-compose.yml).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_template.core.config import Settings
from fastapi_template.main import lifespan

pytestmark = pytest.mark.integration

PROBE_PATH = "/_probe/tracing-ping"


# Override autouse fixtures that depend on the shared test DB schema -- the
# lifespan builds its own engine from settings.database_url.
@pytest.fixture(autouse=True)
def reset_db() -> None:
    """No-op: lifespan manages its own engine; no schema/rows needed."""


@pytest.fixture(autouse=True)
async def default_auth_user_in_org() -> None:
    """No-op: lifespan manages its own engine; no schema/rows needed."""


def _build_probe_app() -> FastAPI:
    """Build a throwaway app wired to the real lifespan with one probe route."""
    probe_app = FastAPI(lifespan=lifespan)

    @probe_app.get(PROBE_PATH)
    async def tracing_ping() -> dict[str, str]:
        return {"status": "ok"}

    return probe_app


async def _assert_lifespan_runs_without_tracing(app: FastAPI) -> None:
    async with lifespan(app):
        assert app.state.tracer_provider is None
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(PROBE_PATH)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert app.state.tracer_provider is None


async def test_tracing_noop_when_otel_disabled_and_extra_absent(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fastapi_template.main.settings.database_url", database_url)
    monkeypatch.setattr("fastapi_template.main.settings.otel_enabled", False)
    app = _build_probe_app()

    await _assert_lifespan_runs_without_tracing(app)


async def test_tracing_noop_when_otel_enabled_unset(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OTEL_ENABLED", raising=False)
    default_settings = Settings(DATABASE_URL=database_url)
    assert default_settings.otel_enabled is False
    monkeypatch.setattr("fastapi_template.main.settings", default_settings)
    app = _build_probe_app()

    await _assert_lifespan_runs_without_tracing(app)
