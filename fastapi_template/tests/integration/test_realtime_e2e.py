"""End-to-end integration test for Socket.IO real-time event delivery.

Validates the full round-trip:
  Write-only emitter (simulating worker)
    → AsyncRedisManager (Redis pub/sub)
      → Full AsyncServer (simulating FastAPI)
        → Connected AsyncClient (simulating browser/mobile)

Requires Docker Redis (started by tests/docker-compose.yml).
"""

import asyncio
import socket as stdlib_socket
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
import socketio
import uvicorn

from fastapi_template.realtime.contracts import (
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_STATUS_CHANGED,
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStatusEvent,
)


# Override autouse fixtures that depend on Postgres -- this test only needs Redis.
@pytest.fixture(autouse=True)
def reset_db() -> None:
    """No-op: realtime tests don't use the database."""


@pytest.fixture(autouse=True)
async def default_auth_user_in_org() -> None:
    """No-op: realtime tests don't use the database."""


# Fixed test tenant IDs
ORG_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TASK_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"

# Seconds to wait for events
EVENT_TIMEOUT = 5.0
# Short wait to confirm events do NOT arrive
NO_EVENT_WAIT = 0.5


def _find_free_port() -> int:
    """Find a free TCP port on localhost."""
    with stdlib_socket.socket(stdlib_socket.AF_INET, stdlib_socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _build_server_app(redis_url: str) -> tuple[socketio.ASGIApp, socketio.AsyncServer]:
    """Build a minimal Socket.IO ASGI app for testing.

    The connect handler accepts any ``auth.token`` value and joins
    the room ``org:{auth.org_id}``.  No real JWT validation — this
    test validates the pub/sub transport, not authentication.
    """
    sio = socketio.AsyncServer(
        async_mode="asgi",
        client_manager=socketio.AsyncRedisManager(redis_url),
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )

    @sio.event
    async def connect(
        sid: str,
        environ: dict[str, Any],  # noqa: ARG001 - Required by python-socketio
        auth: dict[str, Any] | None = None,
    ) -> bool:
        if not auth or not auth.get("token"):
            return False
        org_id = auth.get("org_id")
        if org_id:
            await sio.enter_room(sid, f"org:{org_id}")
        return True

    @sio.event
    async def disconnect(sid: str) -> None:
        pass

    sio_asgi = socketio.ASGIApp(sio, socketio_path="socket.io")
    return sio_asgi, sio


async def _start_server(app: socketio.ASGIApp, port: int) -> tuple[uvicorn.Server, asyncio.Task[None]]:
    """Start uvicorn in a background task, wait until it is accepting."""
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())

    # Wait for the server to start accepting connections
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.05)
    else:
        msg = "uvicorn did not start in time"
        raise RuntimeError(msg)

    return server, task


async def _connect_client(port: int, org_id: str) -> socketio.AsyncClient:
    """Connect a Socket.IO client to the test server, joining an org room."""
    client = socketio.AsyncClient(logger=False, engineio_logger=False)
    await client.connect(
        f"http://127.0.0.1:{port}",
        socketio_path="socket.io",
        transports=["websocket"],
        auth={"token": "test-token", "org_id": org_id},
        wait_timeout=EVENT_TIMEOUT,
    )
    return client


class _EventCollector:
    """Collect Socket.IO events into a list, signalling on receipt."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []
        self._got_event = asyncio.Event()

    def handler(self, event_name: str) -> Callable[[dict[str, Any]], Coroutine[Any, Any, None]]:
        """Return a handler function that records events under *event_name*."""

        async def _handler(data: dict[str, Any]) -> None:
            self.events.append((event_name, data))
            self._got_event.set()

        return _handler

    async def wait(self, *, timeout: float = EVENT_TIMEOUT) -> None:
        """Wait until at least one event has been collected."""
        await asyncio.wait_for(self._got_event.wait(), timeout=timeout)

    async def wait_none(self, *, duration: float = NO_EVENT_WAIT) -> None:
        """Wait briefly and assert NO events arrived."""
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(self._got_event.wait(), timeout=duration)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRealtimeRoundTrip:
    """Full pub/sub round-trip via Redis."""

    @pytest.fixture
    async def server_stack(self, redis_url):
        """Start a test Socket.IO server backed by Redis."""
        port = _find_free_port()
        app, sio = _build_server_app(redis_url)
        server, task = await _start_server(app, port)
        yield port, sio
        server.should_exit = True
        await task

    @pytest.fixture
    async def emitter(self, redis_url):
        """Create a write-only emitter backed by the same Redis."""
        mgr = socketio.AsyncRedisManager(redis_url, write_only=True)
        return socketio.AsyncServer(async_mode="asgi", client_manager=mgr)

    async def test_emitter_to_client_round_trip(self, server_stack, emitter):
        """Event emitted by write-only server reaches a connected client via Redis."""
        port, _sio = server_stack
        client = await _connect_client(port, ORG_A)

        collector = _EventCollector()
        client.on(TASK_COMPLETED, collector.handler(TASK_COMPLETED))

        # Allow Redis pub/sub listener to fully initialize
        await asyncio.sleep(1)

        # Emit from the write-only emitter (simulating worker)
        event = TaskCompletedEvent(
            task_id=TASK_ID,
            task_name="process_document",
            result_url="s3://bucket/result.pdf",
            tenant_id=ORG_A,
        )
        await emitter.emit(
            TASK_COMPLETED,
            event.model_dump(mode="json"),
            room=f"org:{ORG_A}",
        )

        await collector.wait()

        assert len(collector.events) == 1
        name, data = collector.events[0]
        assert name == TASK_COMPLETED
        received = TaskCompletedEvent.model_validate(data)
        assert received == event

        await client.disconnect()

    async def test_tenant_isolation(self, server_stack, emitter):
        """Events for org A do NOT reach clients connected to org B."""
        port, _sio = server_stack

        # Client A in org A, Client B in org B
        client_a = await _connect_client(port, ORG_A)
        client_b = await _connect_client(port, ORG_B)

        collector_a = _EventCollector()
        collector_b = _EventCollector()
        client_a.on(TASK_STATUS_CHANGED, collector_a.handler(TASK_STATUS_CHANGED))
        client_b.on(TASK_STATUS_CHANGED, collector_b.handler(TASK_STATUS_CHANGED))

        # Emit to org A only
        event = TaskStatusEvent(
            task_id=TASK_ID,
            task_name="process_document",
            status="RUNNING",
            tenant_id=ORG_A,
        )
        await emitter.emit(
            TASK_STATUS_CHANGED,
            event.model_dump(mode="json"),
            room=f"org:{ORG_A}",
        )

        # Client A should receive it
        await collector_a.wait()
        assert len(collector_a.events) == 1
        _, data = collector_a.events[0]
        received = TaskStatusEvent.model_validate(data)
        assert received == event

        # Client B should NOT receive it
        await collector_b.wait_none()
        assert len(collector_b.events) == 0

        await client_a.disconnect()
        await client_b.disconnect()

    async def test_multiple_events(self, server_stack, emitter):
        """Multiple event types are delivered correctly."""
        port, _sio = server_stack
        client = await _connect_client(port, ORG_A)

        collector = _EventCollector()
        client.on(TASK_STATUS_CHANGED, collector.handler(TASK_STATUS_CHANGED))
        client.on(TASK_COMPLETED, collector.handler(TASK_COMPLETED))
        client.on(TASK_FAILED, collector.handler(TASK_FAILED))

        # Emit status change
        status_event = TaskStatusEvent(
            task_id=TASK_ID,
            task_name="etl_pipeline",
            status="RUNNING",
            tenant_id=ORG_A,
        )
        await emitter.emit(
            TASK_STATUS_CHANGED,
            status_event.model_dump(mode="json"),
            room=f"org:{ORG_A}",
        )
        await collector.wait()

        # Reset event and emit completion
        collector._got_event.clear()
        completed_event = TaskCompletedEvent(
            task_id=TASK_ID,
            task_name="etl_pipeline",
            tenant_id=ORG_A,
        )
        await emitter.emit(
            TASK_COMPLETED,
            completed_event.model_dump(mode="json"),
            room=f"org:{ORG_A}",
        )
        await collector.wait()

        assert len(collector.events) == 2
        assert TaskStatusEvent.model_validate(collector.events[0][1]) == status_event
        assert TaskCompletedEvent.model_validate(collector.events[1][1]) == completed_event

        await client.disconnect()

    async def test_pydantic_serialization_round_trip(self, server_stack, emitter):
        """Pydantic model_dump(mode='json') payloads deserialize correctly on client."""
        port, _sio = server_stack
        client = await _connect_client(port, ORG_A)

        collector = _EventCollector()
        client.on(TASK_FAILED, collector.handler(TASK_FAILED))

        original = TaskFailedEvent(
            task_id=TASK_ID,
            task_name="import_csv",
            error_detail="ValueError: invalid column 'foo'",
            tenant_id=ORG_A,
        )
        await emitter.emit(
            TASK_FAILED,
            original.model_dump(mode="json"),
            room=f"org:{ORG_A}",
        )

        await collector.wait()

        _, data = collector.events[0]
        # Reconstruct the model from the received dict
        received = TaskFailedEvent.model_validate(data)
        assert received == original

        await client.disconnect()

    async def test_no_auth_rejected(self, server_stack):
        """Client without auth token is rejected."""
        port, _sio = server_stack
        client = socketio.AsyncClient(logger=False, engineio_logger=False)
        with pytest.raises(socketio.exceptions.ConnectionError):
            await client.connect(
                f"http://127.0.0.1:{port}",
                socketio_path="socket.io",
                transports=["websocket"],
                wait_timeout=EVENT_TIMEOUT,
            )
