"""OpenTelemetry distributed tracing for the FastAPI application.

This module is only imported lazily from ``main.lifespan`` when
``OTEL_ENABLED=true``; its ``opentelemetry`` dependencies come from the
optional ``otel`` extra (``pip install .[otel]``) and are never required by
the base install.

Spans produced:
    - One server span per HTTP request (FastAPI instrumentation)
    - One child span per database query (SQLAlchemy instrumentation)
    - One client span per outbound httpx request (HTTPX instrumentation)

Each application instance gets its own ``TracerProvider`` stored on
``app.state.tracer_provider``; the process-global provider is never set.
Spans are exported over OTLP gRPC to ``OTEL_EXPORTER_OTLP_ENDPOINT`` when it
is configured.
"""

from fastapi import FastAPI
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from fastapi_template.core.config import settings
from fastapi_template.db import session as db_session


def setup_tracing(app: FastAPI) -> TracerProvider:
    """Create a per-app TracerProvider and instrument FastAPI, SQLAlchemy, and httpx.

    Must run after ``app.state.engine`` is created.

    Args:
        app: The FastAPI application whose lifespan is starting.

    Returns:
        The TracerProvider that owns this app's spans.
    """
    tracer_provider = TracerProvider(resource=Resource.create({SERVICE_NAME: settings.app_name}))
    if settings.otel_exporter_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    # Under a real ASGI server Starlette builds the middleware stack on the
    # lifespan scope, before startup runs; instrument_app only patches the
    # builder, so rebuild for the tracing middleware to take effect.
    app.middleware_stack = app.build_middleware_stack()

    # Request-scoped sessions (SessionDep) use db.session's module-level
    # engine, not app.state.engine, so both need instrumenting.
    SQLAlchemyInstrumentor().instrument(
        engines=[app.state.engine.sync_engine, db_session.engine.sync_engine],
        tracer_provider=tracer_provider,
    )
    HTTPXClientInstrumentor().instrument(tracer_provider=tracer_provider)
    return tracer_provider


def shutdown_tracing(app: FastAPI, tracer_provider: TracerProvider) -> None:
    """Undo all instrumentation installed by ``setup_tracing`` and flush spans.

    The instrumentors patch process-wide state, so they are uninstrumented
    before the provider shuts down; otherwise a later lifespan in the same
    process would find them already instrumented against a dead provider.

    Args:
        app: The FastAPI application whose lifespan is ending.
        tracer_provider: The provider returned by ``setup_tracing``.
    """
    FastAPIInstrumentor.uninstrument_app(app)
    SQLAlchemyInstrumentor().uninstrument()
    HTTPXClientInstrumentor().uninstrument()
    tracer_provider.shutdown()
