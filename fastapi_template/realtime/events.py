"""Helper functions for emitting Socket.IO events to org rooms."""

from __future__ import annotations

import logging
from uuid import UUID

from pydantic import BaseModel

from fastapi_template.realtime.server import get_sio

LOGGER = logging.getLogger(__name__)


async def emit_to_org(org_id: UUID, event: str, data: BaseModel) -> None:
    """Emit a Socket.IO event to all clients in an org room.

    Args:
        org_id: Organization/tenant UUID -- determines the room.
        event: Event name (use constants from contracts.py).
        data: Pydantic model -- serialized via model_dump(mode="json").
    """
    sio = get_sio()
    room = f"org:{org_id}"
    payload = data.model_dump(mode="json")
    try:
        await sio.emit(event, payload, room=room)
    except Exception:
        LOGGER.exception("socketio_emit_failed", extra={"event": event, "room": room})
