"""FastAPI application entrypoint and wiring.

Middleware Order Matters
------------------------
Middleware is executed in the order it's added (top to bottom for requests,
bottom to top for responses). The current recommended order is:

1. CORS - Must be first to handle preflight OPTIONS requests
2. Rate Limiting - Reject early before auth checks
3. Structured Logging - Initialize request context (request_id) early
4. Authentication - Validate JWT and set user context
5. Tenant Isolation - Extract tenant context from authenticated user

Performance Implications
------------------------
- CORS: Minimal overhead, only affects preflight requests
- Rate Limiting: Redis lookup per request (~1-2ms)
- Structured Logging: ContextVar operations, negligible overhead (<0.1ms)
- Authentication: JWT validation (~5-10ms for RS256)
- Tenant Isolation: Database lookup if not cached (~5-20ms)

Each middleware below is commented with configuration requirements.
Uncomment sections as needed for your deployment.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from pydantic import ValidationError
from sqlalchemy import text

from {{ project_slug }}.api.routes import router as api_router
from {{ project_slug }}.core.config import settings
from {{ project_slug }}.core.logging import LoggingMiddleware
from {{ project_slug }}.core.metrics import metrics_app
from {{ project_slug }}.core.pagination import configure_pagination
from {{ project_slug }}.db.session import engine

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
configure_pagination()
add_pagination(app)

if settings.enable_metrics:
    app.mount("/metrics", metrics_app)

# ============================================================================
# Middleware Configuration
# ============================================================================
# Middleware is processed in REVERSE order (last added = first executed)
# Order them carefully to ensure correct request processing flow

# CORS Middleware (Optional)
# Uncomment to enable Cross-Origin Resource Sharing for frontend applications.
# CRITICAL: In production, restrict origins to your actual frontend domains.
# Never use allow_origins=["*"] in production (security risk).
#
# Configuration in .env:
#   CORS_ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
#
# from fastapi.middleware.cors import CORSMiddleware
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.cors_allowed_origins,  # ["http://localhost:3000"]
#     allow_credentials=True,  # Allow cookies/auth headers
#     allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
#     allow_headers=["*"],  # Allow all headers
# )

# Rate Limiting Middleware (Optional)
# Uncomment to enable request rate limiting per IP address.
# Requires: pip install slowapi
#
# Configuration in .env:
#   RATE_LIMIT_ENABLED=true
#   RATE_LIMIT_PER_MINUTE=100
#
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.errors import RateLimitExceeded
# from slowapi.util import get_remote_address
#
# limiter = Limiter(key_func=get_remote_address)
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
#
# # Then in your endpoints:
# # @app.get("/users")
# # @limiter.limit("100/minute")
# # async def list_users(request: Request):
# #     ...
#
# Documentation: https://slowapi.readthedocs.io/

# Structured Logging Middleware
# Automatically adds request_id, user_id, org_id to all logs
# Configuration in .env:
#   REQUEST_ID_HEADER=x-request-id (default)
#   INCLUDE_REQUEST_CONTEXT_IN_LOGS=true (default)
#
# IMPORTANT: Add BEFORE AuthMiddleware to initialize request context early.
# The middleware will:
# 1. Extract or generate request ID from X-Request-ID header
# 2. Store request_id in ContextVar (available throughout request lifecycle)
# 3. After auth completes, extract user_id and org_id from request.state.user
# 4. Make all context available to services via get_logging_context()
#
# Example usage in services:
#   from {{ project_slug }}.core.logging import get_logging_context
#   logger.info("operation", extra=get_logging_context())
#
app.add_middleware(LoggingMiddleware)

# Authentication Middleware (Optional)
# Uncomment to enable JWT authentication for all endpoints
# Public endpoints (/health, /ping, /docs, /openapi.json, /metrics) are
# automatically excluded
#
# Configuration required in .env:
#   AUTH_PROVIDER_TYPE=ory|auth0|keycloak|cognito
#   AUTH_PROVIDER_URL=https://your-auth-provider.com
#   AUTH_PROVIDER_ISSUER=https://your-auth-provider.com/
#   JWT_ALGORITHM=RS256
#   JWT_PUBLIC_KEY=<your-public-key-pem>
#
# from {{ project_slug }}.core.auth import AuthMiddleware
# app.add_middleware(AuthMiddleware)

# Tenant Isolation Middleware (Optional - Multi-Tenant Applications)
# Uncomment to enforce tenant isolation for all endpoints
# CRITICAL: Must be added AFTER AuthMiddleware (requires authenticated user)
#
# This middleware:
# 1. Extracts organization_id from JWT claims, path params, or query params
# 2. Validates user has membership in the organization
# 3. Returns 403 if user doesn't belong to organization
# 4. Stores tenant context in request.state for endpoint use
#
# Configuration in .env:
#   ENFORCE_TENANT_ISOLATION=true  # Enable tenant isolation (default: true)
#
# Usage in endpoints:
#   from {{ project_slug }}.core.tenants import TenantDep
#
#   @router.get("/documents")
#   async def list_documents(tenant: TenantDep) -> list[DocumentRead]:
#       # tenant.organization_id guaranteed to be valid
#       # User verified as member of organization
#       ...
#
# from {{ project_slug }}.core.tenants import TenantIsolationMiddleware
# app.add_middleware(TenantIsolationMiddleware)

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
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
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
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
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


@app.on_event("startup")
async def startup_event() -> None:
    """Validate database connectivity on startup.

    Fails fast if database is unreachable, rather than waiting for first request
    to fail. This ensures the service doesn't start in a degraded state.
    """
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        # Store error message in variable (EM101)
        db_url = settings.database_url
        error_msg = (
            f"Failed to connect to database on startup: {exc}. "
            f"Check DATABASE_URL={db_url}"
        )
        raise RuntimeError(error_msg) from exc


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up resources on graceful shutdown.

    Graceful Shutdown Flow
    ----------------------
    1. Container receives SIGTERM from orchestrator (Kubernetes, Docker)
    2. FastAPI triggers shutdown event handlers
    3. Connection pool is drained (waits for active queries to complete)
    4. All pending database transactions are committed or rolled back
    5. Process exits cleanly

    Why This Matters
    -----------------
    - Prevents connection leaks when scaling down pods
    - Ensures database doesn't accumulate idle connections
    - Allows in-flight requests to complete before termination
    - Critical for zero-downtime deployments in Kubernetes

    Kubernetes Integration
    ----------------------
    Configure terminationGracePeriodSeconds in pod spec (default: 30s):
    ```yaml
    spec:
      terminationGracePeriodSeconds: 30
      containers:
        - name: api
          # Container has 30 seconds to shut down gracefully
    ```

    The engine.dispose() call will block until all connections are closed
    or until the grace period expires, whichever comes first.
    """
    logger.info("Shutting down: draining database connection pool")
    await engine.dispose()
    logger.info("Shutdown complete: all database connections closed")
