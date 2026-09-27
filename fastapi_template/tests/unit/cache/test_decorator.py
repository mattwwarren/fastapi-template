"""Unit tests for the @cached decorator (explicit tenant threading)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import BaseModel

from fastapi_template.cache.decorator import cached
from fastapi_template.core.tenants import TenantContext
from fastapi_template.models.membership import MembershipRole

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")


class _Sample(BaseModel):
    id: int
    name: str


def _tenant() -> TenantContext:
    return TenantContext(organization_id=ORG_ID, user_id=USER_ID, role=MembershipRole.MEMBER)


def _make_fn() -> tuple[Callable[..., Awaitable[_Sample]], list[int]]:
    """Return a decorated fn plus a call-count list it appends to."""
    calls: list[int] = []

    @cached("user", tenant_param="tenant", id_param="user_id", model_class=_Sample)
    async def get_user(*, tenant: object, user_id: str, redis: object) -> _Sample:  # noqa: ARG001
        calls.append(1)
        return _Sample(id=1, name="alice")

    return get_user, calls


async def test_missing_tenant_calls_through_uncached(redis_mock: AsyncMock) -> None:
    calls: list[int] = []

    @cached("user", tenant_param="tenant", id_param="user_id")
    async def get_user(*, user_id: str, redis: object) -> _Sample:  # noqa: ARG001
        calls.append(1)
        return _Sample(id=1, name="alice")

    result = await get_user(user_id="1", redis=redis_mock)

    assert result == _Sample(id=1, name="alice")
    assert calls == [1]
    redis_mock.get.assert_not_called()


async def test_missing_id_calls_through_uncached(redis_mock: AsyncMock) -> None:
    calls: list[int] = []

    @cached("user", tenant_param="tenant", id_param="user_id")
    async def get_user(*, tenant: object, redis: object) -> _Sample:  # noqa: ARG001
        calls.append(1)
        return _Sample(id=1, name="alice")

    result = await get_user(tenant=_tenant(), redis=redis_mock)

    assert result == _Sample(id=1, name="alice")
    assert calls == [1]
    redis_mock.get.assert_not_called()


async def test_cache_hit_short_circuits(redis_mock: AsyncMock) -> None:
    redis_mock.get.return_value = '{"id": 1, "name": "alice"}'
    get_user, calls = _make_fn()

    result = await get_user(tenant=_tenant(), user_id="1", redis=redis_mock)

    assert result == _Sample(id=1, name="alice")
    assert calls == []  # wrapped function body never executed
    redis_mock.set.assert_not_called()


async def test_cache_miss_calls_and_populates(redis_mock: AsyncMock) -> None:
    redis_mock.get.return_value = None
    get_user, calls = _make_fn()

    result = await get_user(tenant=_tenant(), user_id="1", redis=redis_mock)

    assert result == _Sample(id=1, name="alice")
    assert calls == [1]
    redis_mock.set.assert_awaited_once()


async def test_none_result_not_cached(redis_mock: AsyncMock) -> None:
    redis_mock.get.return_value = None

    @cached("user", tenant_param="tenant", id_param="user_id")
    async def get_user(*, tenant: object, user_id: str, redis: object) -> _Sample | None:  # noqa: ARG001
        return None

    result = await get_user(tenant=_tenant(), user_id="1", redis=redis_mock)

    assert result is None
    redis_mock.set.assert_not_called()


async def test_redis_none_flows_cleanly() -> None:
    get_user, calls = _make_fn()

    result = await get_user(tenant=_tenant(), user_id="1", redis=None)

    assert result == _Sample(id=1, name="alice")
    assert calls == [1]


async def test_organization_id_as_tenant_value(redis_mock: AsyncMock) -> None:
    redis_mock.get.return_value = None
    calls: list[int] = []

    @cached("user", tenant_param="organization_id", id_param="user_id", model_class=_Sample)
    async def get_user(*, organization_id: UUID, user_id: str, redis: object) -> _Sample:  # noqa: ARG001
        calls.append(1)
        return _Sample(id=1, name="alice")

    result = await get_user(organization_id=ORG_ID, user_id="1", redis=redis_mock)

    assert result == _Sample(id=1, name="alice")
    assert calls == [1]
    redis_mock.set.assert_awaited_once()


async def test_explicit_ttl_forwarded(redis_mock: AsyncMock) -> None:
    redis_mock.get.return_value = None
    calls: list[int] = []

    @cached("user", tenant_param="tenant", id_param="user_id", ttl=123, model_class=_Sample)
    async def get_user(*, tenant: object, user_id: str, redis: object) -> _Sample:  # noqa: ARG001
        calls.append(1)
        return _Sample(id=1, name="alice")

    await get_user(tenant=_tenant(), user_id="1", redis=redis_mock)

    _key, _data = redis_mock.set.call_args.args
    ttl = redis_mock.set.call_args.kwargs["ex"]
    assert ttl == 123


async def test_hit_returns_typed_model(redis_mock: AsyncMock) -> None:
    redis_mock.get.return_value = '{"id": 7, "name": "bob"}'
    get_user, _calls = _make_fn()

    result = await get_user(tenant=_tenant(), user_id="7", redis=redis_mock)

    assert isinstance(result, _Sample)
    assert result.id == 7


# --------------------------------------------------------------------------- #
# Decoration-time keyword-only enforcement
# --------------------------------------------------------------------------- #
# A positional call to a decorated function leaves id/tenant/redis out of
# ``kwargs``, which silently disables caching (warn + call through). Requiring
# keyword-only params at decoration time turns that misuse into a loud
# ``TypeError`` from Python's own call convention instead.


def test_positional_capable_id_param_raises_at_decoration() -> None:
    with pytest.raises(TypeError, match=r"'user_id' must be keyword-only"):

        @cached("user", tenant_param="tenant", id_param="user_id")
        async def get_user(user_id: str, *, tenant: object, redis: object) -> _Sample:  # noqa: ARG001
            return _Sample(id=1, name="alice")


def test_positional_capable_tenant_param_raises_at_decoration() -> None:
    with pytest.raises(TypeError, match=r"'tenant' must be keyword-only"):

        @cached("user", tenant_param="tenant", id_param="user_id")
        async def get_user(tenant: object, *, user_id: str, redis: object) -> _Sample:  # noqa: ARG001
            return _Sample(id=1, name="alice")


def test_positional_capable_redis_param_raises_at_decoration() -> None:
    with pytest.raises(TypeError, match=r"'redis' must be keyword-only"):

        @cached("user", tenant_param="tenant", id_param="user_id")
        async def get_user(redis: object, *, tenant: object, user_id: str) -> _Sample:  # noqa: ARG001
            return _Sample(id=1, name="alice")


def test_all_positional_signature_raises_at_decoration() -> None:
    with pytest.raises(TypeError, match=r"must be keyword-only"):

        @cached("user", tenant_param="tenant", id_param="user_id")
        async def get_user(tenant: object, user_id: str, redis: object) -> _Sample:  # noqa: ARG001
            return _Sample(id=1, name="alice")


def test_keyword_only_params_decorate_cleanly() -> None:
    get_user, _calls = _make_fn()

    assert callable(get_user)


def test_absent_params_decorate_cleanly() -> None:
    """Params entirely absent from the signature are not enforced (misconfig path stays warn + call-through)."""

    @cached("user", tenant_param="tenant", id_param="user_id")
    async def get_user(session: object) -> _Sample:  # noqa: ARG001
        return _Sample(id=1, name="alice")

    assert callable(get_user)
