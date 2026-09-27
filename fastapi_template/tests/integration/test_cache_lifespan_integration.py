"""Integration tests for Redis DI wiring through the real application lifespan.

Proves end-to-end that ``main.lifespan`` -> ``create_redis_client()`` -> the
module-level ``cache.client.redis_client`` global -> ``get_redis()``/``RedisDep``
resolves a live client inside an actual request, and that shutdown resets the
DI path back to ``None``. Unit tests cover each hop in isolation; only this
test exercises the chain as a whole.

A throwaway ``FastAPI(lifespan=lifespan)`` probe app is used rather than the
production ``app`` singleton so the probe route never leaks into other tests.

Requires Docker Postgres + Redis (started by tests/docker-compose.yml).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from fastapi_template.cache import client as cache_client
from fastapi_template.cache.client import RedisDep, get_redis
from fastapi_template.main import lifespan

pytestmark = pytest.mark.integration

PROBE_PATH = "/_probe/redis-ping"


# Override autouse fixtures that depend on the shared test DB schema -- the
# lifespan builds its own engine from settings.database_url.
@pytest.fixture(autouse=True)
def reset_db() -> None:
    """No-op: lifespan manages its own engine; no schema/rows needed."""


@pytest.fixture(autouse=True)
async def default_auth_user_in_org() -> None:
    """No-op: lifespan manages its own engine; no schema/rows needed."""


@pytest.fixture(autouse=True)
def _reset_redis_client_global() -> Generator[None]:
    """Isolate the module-level redis_client global mutated by the lifespan."""
    cache_client.redis_client = None
    yield
    cache_client.redis_client = None


def _build_probe_app() -> FastAPI:
    """Build a throwaway app wired to the real lifespan with one RedisDep route."""
    probe_app = FastAPI(lifespan=lifespan)

    @probe_app.get(PROBE_PATH)
    async def redis_ping(redis: RedisDep) -> dict[str, bool]:
        if redis is None:
            return {"connected": False}
        # Prove liveness, not just non-None: ping raises if the client is dead.
        await redis.ping()
        return {"connected": True}

    return probe_app


async def _get_redis_value() -> object:
    """Resolve the DI dependency directly, as FastAPI would."""
    agen = get_redis()
    return await agen.__anext__()


async def test_redis_dep_resolves_live_client_through_real_lifespan(
    database_url: str,
    redis_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fastapi_template.main.settings.database_url", database_url)
    monkeypatch.setattr("fastapi_template.main.settings.redis_url", redis_url)
    app = _build_probe_app()

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(PROBE_PATH)

    assert response.status_code == 200
    assert response.json() == {"connected": True}
    # Shutdown must reset the DI path: a closed client must not keep being injected.
    assert await _get_redis_value() is None


async def test_redis_dep_yields_none_when_redis_unset(
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fastapi_template.main.settings.database_url", database_url)
    monkeypatch.setattr("fastapi_template.main.settings.redis_url", None)
    app = _build_probe_app()

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(PROBE_PATH)

    assert response.status_code == 200
    assert response.json() == {"connected": False}
