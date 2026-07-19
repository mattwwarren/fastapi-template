"""Unit tests for cache key generation (multi-tenant + versioning)."""

from __future__ import annotations

from uuid import UUID

import pytest

from fastapi_template.cache.keys import (
    DEFAULT_KEY_VERSION,
    GLOBAL_TENANT_SENTINEL,
    KEY_SEPARATOR,
    TENANT_PREFIX_FORMAT,
    build_cache_key,
)
from fastapi_template.core.tenants import TenantContext
from fastapi_template.models.membership import MembershipRole

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")
RESOURCE_ID = UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture(autouse=True)
def _default_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force a deterministic prefix/app_name for key assertions."""
    monkeypatch.setattr("fastapi_template.core.config.settings.cache_key_prefix", "")
    monkeypatch.setattr("fastapi_template.core.config.settings.app_name", "fastapi_template")


def _tenant() -> TenantContext:
    return TenantContext(organization_id=ORG_ID, user_id=USER_ID, role=MembershipRole.MEMBER)


def test_basic_key_with_tenant_context() -> None:
    """A TenantContext supplies organization_id for the tenant segment."""
    key = build_cache_key("user", RESOURCE_ID, tenant=_tenant())

    assert key == f"fastapi_template:tenant-{ORG_ID}:user:{RESOURCE_ID}:v1"


def test_basic_key_with_organization_id() -> None:
    """A bare organization_id is accepted without a TenantContext."""
    key = build_cache_key("user", RESOURCE_ID, organization_id=ORG_ID)

    assert key == f"fastapi_template:tenant-{ORG_ID}:user:{RESOURCE_ID}:v1"


def test_global_sentinel_when_tenant_omitted() -> None:
    """Genuinely global entries fall back to the global sentinel (no error)."""
    key = build_cache_key("health", "status")

    assert key == f"fastapi_template:tenant-{GLOBAL_TENANT_SENTINEL}:health:status:v1"


def test_custom_version() -> None:
    """The version segment reflects an explicit version argument."""
    key = build_cache_key("user", RESOURCE_ID, organization_id=ORG_ID, version="v2")

    assert key.endswith(":v2")
    assert key == f"fastapi_template:tenant-{ORG_ID}:user:{RESOURCE_ID}:v2"


def test_suffix_appended() -> None:
    """A suffix is appended after the version segment."""
    key = build_cache_key("user", RESOURCE_ID, organization_id=ORG_ID, suffix="with_memberships")

    assert key == f"fastapi_template:tenant-{ORG_ID}:user:{RESOURCE_ID}:v1:with_memberships"


def test_custom_cache_key_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """cache_key_prefix overrides app_name as the leading segment."""
    monkeypatch.setattr("fastapi_template.core.config.settings.cache_key_prefix", "svc")

    key = build_cache_key("user", RESOURCE_ID, organization_id=ORG_ID)

    assert key.startswith("svc:")


def test_prefix_falls_back_to_app_name() -> None:
    """When cache_key_prefix is empty, app_name is used as the prefix."""
    key = build_cache_key("user", RESOURCE_ID, organization_id=ORG_ID)

    assert key.startswith("fastapi_template:")


def test_string_identifier() -> None:
    """String identifiers are used verbatim."""
    key = build_cache_key("session", "abc123", organization_id=ORG_ID)

    assert key == f"fastapi_template:tenant-{ORG_ID}:session:abc123:v1"


def test_tenant_context_takes_precedence_over_organization_id() -> None:
    """When both are supplied, the TenantContext organization wins."""
    other_org = UUID("99999999-9999-9999-9999-999999999999")

    key = build_cache_key("user", RESOURCE_ID, tenant=_tenant(), organization_id=other_org)

    assert f"tenant-{ORG_ID}" in key
    assert f"tenant-{other_org}" not in key


def test_module_constants_drive_key_format() -> None:
    """Built keys must use the module-level constants, not re-typed literals."""
    key = build_cache_key("user", RESOURCE_ID, tenant=_tenant())

    parts = key.split(KEY_SEPARATOR)
    assert parts[1] == TENANT_PREFIX_FORMAT.format(ORG_ID)
    assert parts[-1] == DEFAULT_KEY_VERSION
    assert KEY_SEPARATOR == ":"
    assert GLOBAL_TENANT_SENTINEL == "global"
