"""Read-only endpoint that publishes Socket.IO event schemas in OpenAPI.

The endpoint itself is never called at runtime -- it exists solely so that
``openapi-typescript`` generates TypeScript types for every event payload.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from fastapi_template.realtime.contracts import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskProgressEvent,
    TaskStatusEvent,
)

router = APIRouter(tags=["realtime"])


class RealtimeEventCatalogResponse(BaseModel):
    """Response wrapper that references each event model by name."""

    task_status_changed: TaskStatusEvent
    task_progress: TaskProgressEvent
    task_completed: TaskCompletedEvent
    task_failed: TaskFailedEvent


@router.get(
    "/realtime/events",
    response_model=RealtimeEventCatalogResponse,
    summary="Socket.IO event schema catalog",
    description=(
        "Returns the schema catalog of all Socket.IO events. "
        "This endpoint exists to publish event payload schemas in the OpenAPI spec "
        "for TypeScript type generation. It is not intended for runtime use."
    ),
)
async def get_realtime_event_catalog() -> RealtimeEventCatalogResponse:
    """Return event catalog (schema-only endpoint)."""
    msg = "This endpoint is for OpenAPI schema generation only"
    raise NotImplementedError(msg)
