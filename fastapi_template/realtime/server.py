"""Socket.IO server with JWT authentication and Redis pub/sub."""

from __future__ import annotations

import logging
from typing import Any

import socketio

from fastapi_template.core.config import settings

LOGGER = logging.getLogger(__name__)

# Module-level server instance, initialized lazily by init_sio()
_sio: socketio.AsyncServer | None = None
_sio_app: socketio.ASGIApp | None = None


def _build_cors_origins() -> str | list[str]:
    """Determine CORS origins for Socket.IO."""
    if settings.socketio_cors_origins is not None:
        return [o.strip() for o in settings.socketio_cors_origins.split(",") if o.strip()]
    return settings.cors_allowed_origins


def init_sio() -> tuple[socketio.AsyncServer, socketio.ASGIApp]:
    """Create and configure the Socket.IO server.

    If REDIS_URL is set, uses AsyncRedisManager for cross-process pub/sub.
    Otherwise uses in-memory manager (single-process only).
    """
    global _sio, _sio_app  # noqa: PLW0603

    cors = _build_cors_origins()

    kwargs: dict[str, Any] = {
        "async_mode": "asgi",
        "cors_allowed_origins": cors,
        "logger": False,
        "engineio_logger": False,
    }

    if settings.redis_url:
        mgr = socketio.AsyncRedisManager(settings.redis_url)
        kwargs["client_manager"] = mgr
        LOGGER.info("socketio_redis_manager_enabled", extra={"redis_url": settings.redis_url.split("@")[-1]})

    sio = socketio.AsyncServer(**kwargs)
    _register_handlers(sio)

    sio_app = socketio.ASGIApp(sio, socketio_path="socket.io")
    _sio = sio
    _sio_app = sio_app
    return sio, sio_app


def get_sio() -> socketio.AsyncServer:
    """Get the Socket.IO server instance."""
    if _sio is None:
        msg = "Socket.IO server not initialized. Call init_sio() first."
        raise RuntimeError(msg)
    return _sio


def get_sio_app() -> socketio.ASGIApp:
    """Get the Socket.IO ASGI app for mounting."""
    if _sio_app is None:
        msg = "Socket.IO app not initialized. Call init_sio() first."
        raise RuntimeError(msg)
    return _sio_app


def _register_handlers(sio: socketio.AsyncServer) -> None:
    """Register Socket.IO event handlers."""

    @sio.event
    async def connect(
        sid: str,
        environ: dict[str, Any],  # noqa: ARG001 - Required by python-socketio handler signature
        auth: dict[str, Any] | None = None,
    ) -> bool | None:
        """Handle client connection with JWT auth."""
        if auth is None or not isinstance(auth, dict):
            LOGGER.warning("socketio_connect_rejected", extra={"sid": sid, "reason": "no_auth"})
            return False

        token = auth.get("token")
        if not token or not isinstance(token, str):
            LOGGER.warning("socketio_connect_rejected", extra={"sid": sid, "reason": "no_token"})
            return False

        # Import here to avoid circular imports and PEP 563 issues
        from fastapi_template.core.auth import verify_token  # noqa: PLC0415

        claims = await verify_token(token)
        if claims is None:
            LOGGER.warning("socketio_connect_rejected", extra={"sid": sid, "reason": "invalid_token"})
            return False

        # Extract org_id for room assignment
        org_id = claims.get("org_id")
        if org_id:
            room = f"org:{org_id}"
            await sio.enter_room(sid, room)
            LOGGER.info("socketio_connected", extra={"sid": sid, "org_id": org_id, "room": room})
        else:
            LOGGER.info("socketio_connected", extra={"sid": sid, "org_id": None})

        # Save session data for later use
        await sio.save_session(sid, {"user_id": claims.get("sub"), "org_id": org_id})
        return True

    @sio.event
    async def disconnect(sid: str) -> None:
        """Handle client disconnection."""
        LOGGER.info("socketio_disconnected", extra={"sid": sid})
