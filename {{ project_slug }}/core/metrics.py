"""Prometheus ASGI app for /metrics with custom business metrics.

OpenTelemetry auto-instrumentation handles HTTP request/response metrics:
- Request duration/latency histograms
- HTTP status codes (2xx, 4xx, 5xx)
- Request counts by endpoint/method
- Active request gauges

This module defines BUSINESS DOMAIN metrics that track application-specific operations.

Usage Examples:

    # In services/user_service.py
    from {{ project_slug }}.core.metrics import users_created_total

    async def create_user(...):
        user = await db.create(...)
        users_created_total.labels(environment=settings.environment).inc()
        return user

    # In services/document_service.py
    from {{ project_slug }}.core.metrics import document_upload_size_bytes

    async def upload_document(file: UploadFile):
        size_bytes = len(await file.read())
        document_upload_size_bytes.observe(size_bytes)
        ...

    # In database query helper
    from {{ project_slug }}.core.metrics import database_query_duration_seconds
    import time

    start = time.perf_counter()
    result = await db.execute(query)
    duration = time.perf_counter() - start
    database_query_duration_seconds.labels(query_type="select").observe(duration)

    # In API endpoints tracking activity
    from {{ project_slug }}.core.metrics import activity_log_entries_created

    activity_log_entries_created.labels(
        resource_type="organization",
        action="delete"
    ).inc()
"""

from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# Business domain metrics (HTTP metrics come from OpenTelemetry auto-instrumentor)
users_created_total = Counter(
    "users_created_total",
    "Total number of users created",
    ["environment"],
)

organizations_created_total = Counter(
    "organizations_created_total",
    "Total number of organizations created",
    ["environment"],
)

memberships_created_total = Counter(
    "memberships_created_total",
    "Total number of memberships created",
    ["environment"],
)

active_memberships_gauge = Gauge(
    "active_memberships_gauge",
    "Current number of active memberships",
    ["environment"],
)

document_upload_size_bytes = Histogram(
    "document_upload_size_bytes",
    "Document upload file sizes in bytes",
    buckets=[1e5, 1e6, 10e6, 50e6, 100e6, 500e6],
)

database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Database query duration in seconds",
    ["query_type"],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0],
)

activity_log_entries_created = Counter(
    "activity_log_entries_created",
    "Total number of activity log entries created",
    ["resource_type", "action"],
)

metrics_app = make_asgi_app()
