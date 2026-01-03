from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.metrics import metrics_app

configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(api_router)

if settings.enable_metrics:
    app.mount("/metrics", metrics_app)
