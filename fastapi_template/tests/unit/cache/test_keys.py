"""Unit tests for cache key generation with multi-tenancy support."""

from uuid import uuid4

import pytest
from fastapi_template.cache.keys import build_cache_key


class TestBuildCacheKey:
    """Test cache key generation with various scenarios."""

    def test_basic_key_generation(self):
        """Basic key includes prefix, tenant, resource, id, and version."""
        user_id = uuid4()
        # Explicitly provide tenant_id to bypass auto-detection
        key = build_cache_key("user", user_id, tenant_id="global")

        assert key.startswith("fastapi_template:")
        assert ":tenant-global:" in key
        assert ":user:" in key
        assert f":{user_id}:" in key
        assert key.endswith(":v1")

    def test_explicit_tenant_id(self):
        """Explicit tenant ID is used in key."""
        org_id = uuid4()
        user_id = uuid4()

        key = build_cache_key("user", user_id, tenant_id=org_id)

        assert f":tenant-{org_id}:" in key

    def test_custom_version(self):
        """Custom version is included in key."""
        user_id = uuid4()
        # Explicitly provide tenant_id to bypass auto-detection
        key = build_cache_key("user", user_id, tenant_id="global", version="v2")

        assert key.endswith(":v2")

    def test_with_suffix(self):
        """Suffix is appended to key."""
        user_id = uuid4()
        # Explicitly provide tenant_id to bypass auto-detection
        key = build_cache_key("user", user_id, tenant_id="global", suffix="with_orgs")

        assert key.endswith(":v1:with_orgs")

    def test_custom_prefix_from_settings(self, test_settings_factory, monkeypatch):
        """Custom cache key prefix from settings is used."""
        # Create settings with custom prefix
        custom_settings = test_settings_factory(cache_key_prefix="myapp", enforce_tenant_isolation=False)
        # Monkeypatch the global settings
        monkeypatch.setattr("fastapi_template.cache.keys.settings", custom_settings)

        user_id = uuid4()
        # Explicitly provide tenant_id to bypass auto-detection
        key = build_cache_key("user", user_id, tenant_id="global")

        assert key.startswith("myapp:")

    def test_string_identifier(self):
        """String identifiers are supported."""
        # Explicitly provide tenant_id to bypass auto-detection
        key = build_cache_key("health", "status", tenant_id="global")

        assert ":health:status:" in key

    @pytest.mark.asyncio
    async def test_tenant_isolation_enforced_without_context(self, test_settings_with_auth):
        """ValueError raised when tenant isolation enforced but no org_id in context."""
        user_id = uuid4()

        # enforce_tenant_isolation=True but no request context
        with pytest.raises(ValueError, match="Tenant isolation is enforced"):
            build_cache_key("user", user_id)

    def test_explicit_global_tenant(self):
        """Explicit global tenant bypasses auto-detection."""
        user_id = uuid4()
        key = build_cache_key("health", user_id, tenant_id="global")

        assert ":tenant-global:" in key
