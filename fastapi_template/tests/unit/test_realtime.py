"""Unit tests for the realtime module.

Tests cover:
- Pydantic event contracts (serialization, defaults, optional fields)
- Socket.IO server initialization and connect handler with JWT auth
- Event emission helpers
- Schema catalog endpoint (OpenAPI integration)
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import socketio
from httpx import ASGITransport, AsyncClient

import fastapi_template.realtime.server as server_mod
from fastapi_template.api.realtime_schemas import get_realtime_event_catalog
from fastapi_template.main import app
from fastapi_template.realtime.contracts import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskProgressEvent,
    TaskStatusEvent,
)
from fastapi_template.realtime.events import emit_to_org
from fastapi_template.realtime.server import get_sio, init_sio

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_sio():
    """Reset Socket.IO module state between tests."""
    server_mod._sio = None
    server_mod._sio_app = None
    yield
    server_mod._sio = None
    server_mod._sio_app = None


# ---------------------------------------------------------------------------
# Contract model tests
# ---------------------------------------------------------------------------


class TestTaskStatusEvent:
    """Tests for TaskStatusEvent serialization."""

    def test_task_status_event_serialization(self) -> None:
        """model_dump(mode='json') produces correct dict with UUID as string."""
        task_id = uuid4()
        tenant_id = uuid4()
        event = TaskStatusEvent(
            task_id=task_id,
            task_name="process_document",
            status="running",
            total_steps=5,
            completed_steps=2,
            status_message="Processing page 2",
            tenant_id=tenant_id,
        )
        dumped = event.model_dump(mode="json")

        assert dumped["task_id"] == str(task_id)
        assert dumped["tenant_id"] == str(tenant_id)
        assert dumped["task_name"] == "process_document"
        assert dumped["status"] == "running"
        assert dumped["total_steps"] == 5
        assert dumped["completed_steps"] == 2
        assert dumped["status_message"] == "Processing page 2"
        assert dumped["error_detail"] is None


class TestTaskProgressEvent:
    """Tests for TaskProgressEvent defaults."""

    def test_task_progress_event_defaults(self) -> None:
        """Default values are set correctly for optional fields."""
        task_id = uuid4()
        event = TaskProgressEvent(task_id=task_id, completed_steps=3)
        dumped = event.model_dump(mode="json")

        assert dumped["task_id"] == str(task_id)
        assert dumped["completed_steps"] == 3
        assert dumped["total_steps"] is None
        assert dumped["status_message"] is None


class TestTaskCompletedEvent:
    """Tests for TaskCompletedEvent field serialization."""

    def test_task_completed_event_fields(self) -> None:
        """All fields serialize correctly including optional result_url."""
        task_id = uuid4()
        tenant_id = uuid4()
        event = TaskCompletedEvent(
            task_id=task_id,
            task_name="generate_report",
            result_url="https://storage.example.com/reports/abc.pdf",
            tenant_id=tenant_id,
        )
        dumped = event.model_dump(mode="json")

        assert dumped["task_id"] == str(task_id)
        assert dumped["task_name"] == "generate_report"
        assert dumped["result_url"] == "https://storage.example.com/reports/abc.pdf"
        assert dumped["tenant_id"] == str(tenant_id)


class TestTaskFailedEvent:
    """Tests for TaskFailedEvent optional error_detail."""

    def test_task_failed_event_optional_error(self) -> None:
        """error_detail is optional and defaults to None."""
        task_id = uuid4()
        tenant_id = uuid4()

        # Without error_detail
        event_no_error = TaskFailedEvent(
            task_id=task_id,
            task_name="import_data",
            tenant_id=tenant_id,
        )
        assert event_no_error.error_detail is None
        dumped = event_no_error.model_dump(mode="json")
        assert dumped["error_detail"] is None

        # With error_detail
        event_with_error = TaskFailedEvent(
            task_id=task_id,
            task_name="import_data",
            error_detail="Connection timeout after 30s",
            tenant_id=tenant_id,
        )
        assert event_with_error.error_detail == "Connection timeout after 30s"


# ---------------------------------------------------------------------------
# Server tests
# ---------------------------------------------------------------------------


class TestInitSio:
    """Tests for init_sio() server creation."""

    @patch("fastapi_template.realtime.server.settings")
    def test_init_sio_creates_server(self, mock_settings: MagicMock) -> None:
        """init_sio() creates an AsyncServer and ASGIApp."""
        mock_settings.redis_url = None
        mock_settings.socketio_cors_origins = None
        mock_settings.cors_allowed_origins = ["http://localhost:3000"]

        sio, sio_app = init_sio()

        assert isinstance(sio, socketio.AsyncServer)
        assert isinstance(sio_app, socketio.ASGIApp)

    @patch("fastapi_template.realtime.server.socketio.AsyncRedisManager")
    @patch("fastapi_template.realtime.server.settings")
    def test_init_sio_with_redis_url(
        self, mock_settings: MagicMock, mock_redis_manager: MagicMock
    ) -> None:
        """When redis_url is set, AsyncRedisManager is used."""
        mock_settings.redis_url = "redis://redis:6379/0"
        mock_settings.socketio_cors_origins = None
        mock_settings.cors_allowed_origins = ["http://localhost:3000"]
        mock_redis_manager.return_value = MagicMock()

        sio, _sio_app = init_sio()

        mock_redis_manager.assert_called_once_with("redis://redis:6379/0")
        assert isinstance(sio, socketio.AsyncServer)


class TestGetSio:
    """Tests for get_sio() accessor."""

    def test_get_sio_before_init_raises(self) -> None:
        """get_sio() raises RuntimeError when server is not initialized."""
        with pytest.raises(RuntimeError, match=r"Socket\.IO server not initialized"):
            get_sio()


class TestConnectHandler:
    """Tests for the Socket.IO connect handler with JWT auth."""

    @patch("fastapi_template.realtime.server.settings")
    def _init_sio_and_get_connect_handler(
        self, mock_settings: MagicMock
    ) -> tuple[socketio.AsyncServer, object]:
        """Helper: init server and extract the connect handler."""
        mock_settings.redis_url = None
        mock_settings.socketio_cors_origins = None
        mock_settings.cors_allowed_origins = ["http://localhost:3000"]

        sio, _ = init_sio()
        # The connect handler is registered on the sio instance's handlers
        connect_handler = sio.handlers["/"]["connect"]
        return sio, connect_handler

    @pytest.mark.asyncio
    async def test_connect_without_auth_rejected(self) -> None:
        """Connection with auth=None is rejected."""
        _sio, handler = self._init_sio_and_get_connect_handler()
        result = await handler("test-sid", {}, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_without_token_rejected(self) -> None:
        """Connection with auth={} (no 'token' key) is rejected."""
        _sio, handler = self._init_sio_and_get_connect_handler()
        result = await handler("test-sid", {}, {})
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_with_invalid_token_rejected(self) -> None:
        """Connection with invalid JWT token is rejected."""
        _sio, handler = self._init_sio_and_get_connect_handler()

        with patch(
            "fastapi_template.core.auth.verify_token",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await handler("test-sid", {}, {"token": "bad-token"})
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_with_valid_token_accepted(self) -> None:
        """Connection with valid JWT token is accepted and enters org room."""
        sio, handler = self._init_sio_and_get_connect_handler()

        org_id = str(uuid4())
        user_id = str(uuid4())
        claims = {"sub": user_id, "org_id": org_id}

        with patch(
            "fastapi_template.core.auth.verify_token",
            new_callable=AsyncMock,
            return_value=claims,
        ):
            # Mock enter_room and save_session since they require actual sio internals
            sio.enter_room = AsyncMock()
            sio.save_session = AsyncMock()
            result = await handler("test-sid", {}, {"token": "valid-token"})

        assert result is True
        # Verify enter_room was called with the correct org room
        sio.enter_room.assert_called_once_with("test-sid", f"org:{org_id}")
        # Verify session was saved with correct data
        sio.save_session.assert_called_once_with(
            "test-sid", {"user_id": user_id, "org_id": org_id}
        )


# ---------------------------------------------------------------------------
# Events tests
# ---------------------------------------------------------------------------


class TestEmitToOrg:
    """Tests for emit_to_org() helper."""

    @pytest.mark.asyncio
    async def test_emit_to_org_calls_sio_emit(self) -> None:
        """emit_to_org() calls sio.emit with correct room and serialized payload."""
        org_id = uuid4()
        task_id = uuid4()
        event_data = TaskStatusEvent(
            task_id=task_id,
            task_name="test_task",
            status="running",
            tenant_id=org_id,
        )

        mock_sio = AsyncMock()
        with patch("fastapi_template.realtime.events.get_sio", return_value=mock_sio):
            await emit_to_org(org_id, "task_status_changed", event_data)

        expected_payload = event_data.model_dump(mode="json")
        mock_sio.emit.assert_called_once_with(
            "task_status_changed",
            expected_payload,
            room=f"org:{org_id}",
        )

    @pytest.mark.asyncio
    async def test_emit_to_org_handles_exception(self) -> None:
        """emit_to_org() swallows exceptions from sio.emit without propagating."""
        org_id = uuid4()
        task_id = uuid4()
        event_data = TaskStatusEvent(
            task_id=task_id,
            task_name="test_task",
            status="failed",
            tenant_id=org_id,
        )

        mock_sio = AsyncMock()
        mock_sio.emit.side_effect = ConnectionError("Redis connection lost")
        with patch("fastapi_template.realtime.events.get_sio", return_value=mock_sio):
            # Should not raise
            await emit_to_org(org_id, "task_status_changed", event_data)


# ---------------------------------------------------------------------------
# Schema endpoint tests
# ---------------------------------------------------------------------------


class TestRealtimeSchemaEndpoint:
    """Tests for the /realtime/events schema catalog endpoint."""

    @pytest.mark.asyncio
    async def test_realtime_events_endpoint_raises_not_implemented(self) -> None:
        """The endpoint handler raises NotImplementedError (schema-only endpoint)."""
        with pytest.raises(NotImplementedError, match="OpenAPI schema generation only"):
            await get_realtime_event_catalog()

    @pytest.mark.asyncio
    async def test_realtime_schema_in_openapi(self) -> None:
        """OpenAPI spec includes TaskStatusEvent and related schemas."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")

        assert response.status_code == HTTPStatus.OK
        openapi = response.json()
        schemas = openapi["components"]["schemas"]

        assert "TaskStatusEvent" in schemas
        assert "TaskProgressEvent" in schemas
        assert "TaskCompletedEvent" in schemas
        assert "TaskFailedEvent" in schemas
        assert "RealtimeEventCatalogResponse" in schemas
