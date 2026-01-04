"""FastAPI application entrypoint and wiring."""

from fastapi import FastAPI
from fastapi_pagination import add_pagination

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.metrics import metrics_app
from app.core.pagination import configure_pagination

app = FastAPI(title=settings.app_name)
app.include_router(api_router)
configure_pagination()
add_pagination(app)

if settings.enable_metrics:
    app.mount("/metrics", metrics_app)
