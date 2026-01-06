"""FastAPI application entrypoint and wiring."""

from fastapi import FastAPI
from fastapi_pagination import add_pagination
from sqlalchemy import text

from {{ project_slug }}.api.routes import router as api_router
from {{ project_slug }}.core.config import settings
from {{ project_slug }}.core.metrics import metrics_app
from {{ project_slug }}.core.pagination import configure_pagination
from {{ project_slug }}.db.session import engine

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
configure_pagination()
add_pagination(app)

if settings.enable_metrics:
    app.mount("/metrics", metrics_app)


@app.on_event("startup")
async def startup_event() -> None:
    """Validate database connectivity on startup.

    Fails fast if database is unreachable, rather than waiting for first request
    to fail. This ensures the service doesn't start in a degraded state.
    """
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as e:
        raise RuntimeError(
            f"Failed to connect to database on startup: {e}. "
            f"Check DATABASE_URL={settings.database_url}"
        ) from e
