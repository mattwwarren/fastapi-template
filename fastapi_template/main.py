"""FastAPI application entrypoint and middleware configuration.

Middleware Execution Order
--------------------------
FastAPI/Starlette middleware executes in REVERSE order of addition:
- Last added middleware = FIRST to process requests
- First added middleware = LAST to process requests

Verified request flow for the active stack (empirically confirmed via
app.user_middleware):
1. LoggingMiddleware - added last, executes first
2. AsyncRateLimitMiddleware (rate limiting) - added second
3. CORSMiddleware - added first, executes last before endpoint

Response flow is the reverse (CORS first, Logging last).

AuthMiddleware and TenantIsolationMiddleware ship commented out below.
Their app.add_middleware() calls are deliberately placed in this order:
Tenant, then Auth, then Logging (last) - so that uncommenting them in
place yields this execution order:
    Logging -> Auth -> Tenant -> AsyncRateLimitMiddleware -> CORS
Auth runs before Tenant so request.state.user exists when tenant
isolation checks it. See ARCHITECTURE.md's "Request lifecycle" section.

Performance Implications
------------------------
- CORS: Minimal overhead, only affects preflight requests
- Rate Limiting: Redis lookup per request when REDIS_URL is set (~1-2ms),
  bounded by Redis socket timeouts and falling back to in-process memory on
  outage; in-process memory otherwise (per-worker, not shared across replicas)
- Structured Logging: ContextVar operations, negligible overhead (<0.1ms)
- Authentication: JWT validation (~5-10ms for RS256)
- Tenant Isolation: Database lookup if not cached (~5-20ms)

Each middleware below is commented with configuration requirements.
Uncomment sections as needed for your deployment.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from inspect import iscoroutinefunction

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from pydantic import ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import _check_limits, _find_route_handler, _should_exempt
from slowapi.util import get_remote_address
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from fastapi_template.api.admin import router as admin_internal_router
from fastapi_template.api.admin import webhooks_router as admin_webhooks_router
from fastapi_template.api.routes import router as api_router
from fastapi_template.cache import client as cache_client
from fastapi_template.cache.client import create_redis_client
from fastapi_template.core.config import ConfigurationError, settings
from fastapi_template.core.logging import LoggingMiddleware
from fastapi_template.core.metrics import metrics_app
from fastapi_template.core.pagination import configure_pagination
from fastapi_template.db.session import PoolConfig, create_db_engine, create_session_maker
from fastapi_template.realtime.server import get_sio_app, init_sio

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - initialize and cleanup resources.

    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    Initializes database engine and session maker, validates connectivity,
    and ensures proper cleanup on shutdown.

    This pattern is pytest-xdist compatible because each test worker can
    inject its own engine/session_maker into app.state via fixtures,
    rather than relying on module-level globals.

    Yields:
        None after startup completes, resumes for shutdown on context exit.
    """
    # Startup: Validate configuration first (fail fast on misconfiguration)
    try:
        config_warnings = settings.validate_config()
        for warning in config_warnings:
            logger.warning("Configuration warning: %s", warning)
    except ConfigurationError:
        logger.exception("Configuration validation failed")
        raise

    # Startup: Initialize database engine and session maker
    pool_config = PoolConfig(
        size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        timeout=settings.db_pool_timeout,
        recycle=settings.db_pool_recycle,
        pre_ping=settings.db_pool_pre_ping,
    )
    app.state.engine = create_db_engine(
        settings.database_url,
        echo=settings.sqlalchemy_echo,
        pool=pool_config,
    )
    app.state.async_session_maker = create_session_maker(app.state.engine)

    # Validate database connectivity (fail fast)
    try:
        async with app.state.engine.begin() as connection:
            await connection.execute(text("SELECT 1"))

        # Sanitize URL before logging (remove credentials)
        safe_url = str(settings.database_url).split("@")[-1]
        logger.info("Database connection successful: %s", safe_url)
    except Exception as exc:
        db_url = settings.database_url
        error_msg = f"Failed to connect to database on startup: {exc}. Check DATABASE_URL={db_url}"
        raise RuntimeError(error_msg) from exc

    # Initialize Socket.IO server (optional - requires no external services)
    init_sio()
    sio_app = get_sio_app()
    app.mount("/ws", sio_app)
    logger.info("socketio_mounted", extra={"path": "/ws/socket.io/"})

    # Initialize Redis cache client (optional - graceful degradation).
    # Enablement derives from REDIS_URL presence; an unset or unreachable
    # Redis leaves cache operations as silent no-ops.
    app.state.redis_client = await create_redis_client()
    if app.state.redis_client is not None:
        logger.info("Redis caching enabled")
    else:
        logger.warning("Redis caching disabled - cache operations will be no-ops")

    # Initialize OpenTelemetry tracing (optional - requires the 'otel' extra).
    # Imported lazily so the base install never needs opentelemetry.
    if settings.otel_enabled:
        from fastapi_template.core.tracing import setup_tracing  # noqa: PLC0415

        app.state.tracer_provider = setup_tracing(app)
        logger.info("OpenTelemetry tracing enabled")
    else:
        app.state.tracer_provider = None

    yield

    # Shutdown: Clean up resources
    if app.state.tracer_provider is not None:
        from fastapi_template.core.tracing import shutdown_tracing  # noqa: PLC0415

        shutdown_tracing(app, app.state.tracer_provider)
        logger.info("OpenTelemetry tracing shut down")
    logger.info("Shutting down: draining database connection pool")
    await app.state.engine.dispose()
    if app.state.redis_client is not None:
        await app.state.redis_client.aclose()
        # Reset the DI global too, so get_redis()/RedisDep never inject a closed client.
        cache_client.redis_client = None
        logger.info("Redis cache connection closed")
    logger.info("Shutdown complete: all database connections closed")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(api_router)
# Internal/admin endpoints (/_admin namespace)
# SECURITY: Must be blocked from external access via Traefik
app.include_router(admin_internal_router)
app.include_router(admin_webhooks_router)
configure_pagination()
add_pagination(app)

if settings.enable_metrics:
    app.mount("/metrics", metrics_app)

# ============================================================================
# Middleware Configuration
# ============================================================================
# Middleware is processed in REVERSE order (last added = first executed)
# Order them carefully to ensure correct request processing flow

# CORS Middleware
# Cross-Origin Resource Sharing for frontend applications.
# CRITICAL: In production, restrict origins to your actual frontend domains.
# Never use allow_origins=["*"] in production (security risk).
#
# Configuration in .env:
#   CORS_ALLOWED_ORIGINS=http://localhost:3000
#
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,  # ['http://localhost:3000']
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],  # Explicit list
    allow_headers=["Authorization", "Content-Type"],  # Explicit list
)


# Rate Limiting Middleware
# Protects against brute force attacks and DoS by limiting requests per IP.
# Default limits: 100 requests/minute, 2000 requests/hour
#
# Requires: pip install slowapi
#
# Configuration in .env:
#   RATE_LIMIT_ENABLED=true (default)
#   RATE_LIMIT_PER_MINUTE=100 (default)
#   RATE_LIMIT_PER_HOUR=2000 (default)
#
# Storage backend follows REDIS_URL: set -> Redis-backed (shared across
# replicas/workers); unset -> in-process memory (per-worker only). Redis
# outages use slowapi's in-process fallback with the same default limits after
# the configured socket timeouts expire.
#
# Per-endpoint limits can override defaults:
#   @router.get("/sensitive-endpoint")
#   @limiter.limit("10/minute")
#   async def sensitive_operation(request: Request):
#       ...
#
# Documentation: https://slowapi.readthedocs.io/
def _rate_limit_storage_uri() -> str | None:
    """Resolve the slowapi storage backend from REDIS_URL.

    Mirrors realtime.server's REDIS_URL-presence convention: set -> Redis-
    backed (shared across replicas/workers); unset -> in-process memory
    (per-worker limits only), which is safe only for a single-replica,
    single-worker deployment.
    """
    if not settings.redis_url:
        logger.warning(
            "Rate limiting storage is in-process memory (REDIS_URL not set) - "
            "limits are per-worker and NOT shared across replicas"
        )
        return None

    safe_url = settings.redis_url.split("@")[-1]
    logger.info("Rate limiting storage backend: Redis (%s)", safe_url)
    return settings.redis_url


class AsyncRateLimitMiddleware(BaseHTTPMiddleware):
    """Run slowapi's synchronous storage checks outside the event loop."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        app = request.app
        limiter: Limiter = app.state.limiter

        if not limiter.enabled:
            return await call_next(request)

        handler = _find_route_handler(app.routes, request.scope)
        if _should_exempt(limiter, handler):
            return await call_next(request)

        exception_handler, should_inject_headers, exc = await run_in_threadpool(
            _check_limits, limiter, request, handler, app
        )
        if exception_handler is not None and exc is not None:
            if iscoroutinefunction(exception_handler):
                return await exception_handler(request, exc)
            return exception_handler(request, exc)

        response = await call_next(request)
        if should_inject_headers:
            response = limiter._inject_headers(response, request.state.view_rate_limit)
        return response


def _rate_limit_storage_options() -> dict[str, int]:
    """Return numeric Redis socket timeouts required by redis-py."""
    return {
        "socket_connect_timeout": settings.redis_socket_connect_timeout,
        "socket_timeout": settings.redis_socket_timeout,
    }


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute", "2000/hour"],
    storage_uri=_rate_limit_storage_uri(),
    # slowapi annotates these options as str-only, but redis-py requires numeric values.
    storage_options=_rate_limit_storage_options(),
    in_memory_fallback=["100/minute", "2000/hour"],
    in_memory_fallback_enabled=True,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(AsyncRateLimitMiddleware)

# Tenant Isolation Middleware (DISABLED - Authentication Required)
# Multi-tenant isolation requires authentication to be enabled first.
#
# ADD-ORDER NOTE: Starlette executes middleware in REVERSE of add order
# (last added runs first). This call is placed BEFORE AuthMiddleware's
# below so that, once both are uncommented, AuthMiddleware executes FIRST
# and this middleware executes SECOND - auth populates request.state.user
# before tenant isolation reads it.
#
# To enable:
#   1. Regenerate project with copier and set auth_enabled=true
#   2. Or manually enable AuthMiddleware below, then uncomment:
#
# from fastapi_template.core.tenants import TenantIsolationMiddleware
# app.add_middleware(TenantIsolationMiddleware)

# Authentication Middleware (DISABLED)
# To enable authentication:
#   1. Regenerate project with copier and set auth_enabled=true
#   2. Or manually uncomment the following and configure .env:
#
# ADD-ORDER NOTE: placed AFTER TenantIsolationMiddleware above so this
# middleware executes BEFORE it (auth must run before tenant isolation).
# See "Middleware Execution Order" in the module docstring.
#
# from fastapi_template.core.auth import AuthMiddleware
# app.add_middleware(AuthMiddleware)
#
# Configuration required in .env:
#   AUTH_PROVIDER_TYPE=ory|auth0|keycloak|cognito
#   AUTH_PROVIDER_URL=https://your-auth-provider.com
#   AUTH_PROVIDER_ISSUER=https://your-auth-provider.com/
#   JWT_ALGORITHM=RS256
#   JWT_PUBLIC_KEY=<your-public-key-pem>

# Structured Logging Middleware
# Automatically adds request_id, user_id, org_id to all logs
# Configuration in .env:
#   REQUEST_ID_HEADER=x-request-id (default)
#   INCLUDE_REQUEST_CONTEXT_IN_LOGS=true (default)
#
# IMPORTANT: This middleware executes FIRST (before Auth/Tenant above) so
# request context is available for the entire request lifecycle. Because
# Starlette runs middleware in reverse of add order, this app.add_middleware
# call is placed LAST (below AuthMiddleware/TenantIsolationMiddleware) -
# execution order is Logging -> Auth -> Tenant, add order is the reverse.
# The middleware will:
# 1. Extract or generate request ID from X-Request-ID header
# 2. Store request_id in ContextVar (available throughout request lifecycle)
# 3. After auth completes, extract user_id and org_id from request.state.user
# 4. Make all context available to services via get_logging_context()
#
# Example usage in services:
#   from fastapi_template.core.logging import get_logging_context
#   logger.info("operation", extra=get_logging_context())
#
app.add_middleware(LoggingMiddleware)

# Global Exception Handlers
# These provide consistent error responses across the entire API


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,  # noqa: ARG001 - Required by FastAPI signature
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors from request payloads.

    Returns structured 422 response with detailed validation error information.
    FastAPI uses RequestValidationError for request body validation failures.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(
    request: Request,  # noqa: ARG001 - Required by FastAPI signature
    exc: ValidationError,
) -> JSONResponse:
    """Handle Pydantic validation errors from internal model validation.

    Returns structured 422 response with detailed validation error information.
    This catches ValidationError raised in service layer or business logic.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "error_code": "VALIDATION_ERROR",
            "message": "Data validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(ValueError)
async def value_error_exception_handler(
    request: Request,  # noqa: ARG001 - Required by FastAPI signature
    exc: ValueError,
) -> JSONResponse:
    """Handle ValueError as 400 Bad Request.

    ValueError typically indicates invalid input data that passed initial
    validation but failed business logic validation (e.g., invalid UUID format,
    out-of-range values).
    """
    error_message = str(exc) if str(exc) else "Invalid value provided"
    logger.warning("ValueError in request: %s", error_message, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status_code": status.HTTP_400_BAD_REQUEST,
            "error_code": "INVALID_VALUE",
            "message": error_message,
        },
    )


@app.exception_handler(TypeError)
async def type_error_exception_handler(
    request: Request,  # noqa: ARG001 - Required by FastAPI signature
    exc: TypeError,
) -> JSONResponse:
    """Handle TypeError as 400 Bad Request.

    TypeError typically indicates incorrect data types in the request,
    which suggests a client error in how the API is being called.
    """
    error_message = str(exc) if str(exc) else "Invalid type provided"
    logger.warning("TypeError in request: %s", error_message, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status_code": status.HTTP_400_BAD_REQUEST,
            "error_code": "INVALID_TYPE",
            "message": error_message,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request,  # noqa: ARG001 - Required by FastAPI signature
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions as 500 Internal Server Error.

    Logs full exception details for debugging but returns sanitized message
    to clients to avoid leaking internal implementation details.
    This is a catch-all handler for any unhandled exceptions.
    """
    # Log full exception details for debugging
    logger.exception("Unhandled exception in request", exc_info=exc)

    # Return sanitized error to client (no internal details)
    sanitized_message = "An internal server error occurred"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "error_code": "INTERNAL_ERROR",
            "message": sanitized_message,
        },
    )
