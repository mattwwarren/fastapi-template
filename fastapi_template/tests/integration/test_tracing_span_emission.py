"""Integration test for OpenTelemetry span emission through the real lifespan.

Proves end-to-end that with ``OTEL_ENABLED=true`` a request to ``/health``
produces a FastAPI server span plus a child span for its database query.

``/health`` resolves its session through ``db.session``'s module-level
session maker (not ``app.state``), so the test points that global at the
worker database; tracing must instrument it for the child span to appear.

The real ``BatchSpanProcessor``/``OTLPSpanExporter`` pipeline is still
constructed against an unreachable endpoint; an ``InMemorySpanExporter`` is
attached alongside it to observe the finished spans.

Requires Docker Postgres (started by tests/docker-compose.yml) and the
``otel`` extra (``uv sync --extra otel``).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from fastapi_template.api.health import router as health_router
from fastapi_template.db import session as db_session
from fastapi_template.db.session import create_session_maker
from fastapi_template.main import lifespan

OTEL_EXTRA_REASON = "requires the otel extra: uv sync --extra otel"
sdk_trace = pytest.importorskip("opentelemetry.sdk.trace", reason=OTEL_EXTRA_REASON)
sdk_export = pytest.importorskip("opentelemetry.sdk.trace.export", reason=OTEL_EXTRA_REASON)
sdk_in_memory = pytest.importorskip(
    "opentelemetry.sdk.trace.export.in_memory_span_exporter",
    reason=OTEL_EXTRA_REASON,
)
otel_trace = pytest.importorskip("opentelemetry.trace", reason=OTEL_EXTRA_REASON)

pytestmark = [pytest.mark.integration, pytest.mark.otel]

UNREACHABLE_OTLP_ENDPOINT = "http://127.0.0.1:4317"


# Override autouse fixtures that depend on the shared test DB schema -- the
# lifespan builds its own engine from settings.database_url.
@pytest.fixture(autouse=True)
def reset_db() -> None:
    """No-op: lifespan manages its own engine; no schema/rows needed."""


@pytest.fixture(autouse=True)
async def default_auth_user_in_org() -> None:
    """No-op: lifespan manages its own engine; no schema/rows needed."""


def _build_probe_app() -> FastAPI:
    """Build a throwaway app wired to the real lifespan and the /health route."""
    probe_app = FastAPI(lifespan=lifespan)
    probe_app.include_router(health_router)
    return probe_app


async def test_health_request_emits_server_span_with_db_child_span(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fastapi_template.main.settings.database_url", database_url)
    monkeypatch.setattr("fastapi_template.main.settings.otel_enabled", True)
    monkeypatch.setattr("fastapi_template.main.settings.otel_exporter_endpoint", UNREACHABLE_OTLP_ENDPOINT)
    # Bound the shutdown flush's export retries against the unreachable collector.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", "1")
    request_engine = create_async_engine(database_url, poolclass=NullPool)
    monkeypatch.setattr(db_session, "engine", request_engine)
    monkeypatch.setattr(db_session, "async_session_maker", create_session_maker(request_engine))
    app = _build_probe_app()
    # Under uvicorn, Starlette builds the middleware stack on the lifespan
    # scope before startup runs; tracing must still take effect afterwards.
    app.middleware_stack = app.build_middleware_stack()
    exporter = sdk_in_memory.InMemorySpanExporter()

    try:
        async with lifespan(app):
            assert isinstance(app.state.tracer_provider, sdk_trace.TracerProvider)
            app.state.tracer_provider.add_span_processor(sdk_export.SimpleSpanProcessor(exporter))
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/health")
            spans = exporter.get_finished_spans()
    finally:
        await request_engine.dispose()

    assert response.status_code == 200
    server_spans = [span for span in spans if span.kind == otel_trace.SpanKind.SERVER and "/health" in span.name]
    assert len(server_spans) == 1
    server_span = server_spans[0]
    db_spans = [
        span
        for span in spans
        if span.parent is not None
        and span.parent.span_id == server_span.context.span_id
        and "SELECT" in span.name.upper()
    ]
    assert len(db_spans) == 1
    assert db_spans[0].context.trace_id == server_span.context.trace_id
