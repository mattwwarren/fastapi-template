"""Unit tests for cache key generation with multi-tenancy support."""

from uuid import uuid4

import pytest

from fastapi_template.cache.keys import build_cache_key


class TestBuildCacheKey:
    """Test cache key generation with various scenarios."""

    def test_basic_key_generation(self, test_settings):
        """Basic key includes prefix, tenant, resource, id, and version."""
        user_id = uuid4()
        key = build_cache_key("user", user_id)

        assert key.startswith("fastapi_template:")
        assert ":tenant-global:" in key
        assert ":user:" in key
        assert f":{user_id}:" in key
        assert key.endswith(":v1")

    def test_explicit_tenant_id(self, test_settings):
        """Explicit tenant ID is used in key."""
        org_id = uuid4()
        user_id = uuid4()

        key = build_cache_key("user", user_id, tenant_id=org_id)

        assert f":tenant-{org_id}:" in key

    def test_custom_version(self, test_settings):
        """Custom version is included in key."""
        user_id = uuid4()
        key = build_cache_key("user", user_id, version="v2")

        assert key.endswith(":v2")

    def test_with_suffix(self, test_settings):
        """Suffix is appended to key."""
        user_id = uuid4()
        key = build_cache_key("user", user_id, suffix="with_orgs")

        assert key.endswith(":v1:with_orgs")

    def test_custom_prefix_from_settings(self, test_settings_factory):
        """Custom cache key prefix from settings is used."""
        settings = test_settings_factory(cache_key_prefix="myapp")
        user_id = uuid4()

        key = build_cache_key("user", user_id)

        assert key.startswith("myapp:")

    def test_string_identifier(self, test_settings):
        """String identifiers are supported."""
        key = build_cache_key("health", "status")

        assert ":health:status:" in key

    @pytest.mark.asyncio
    async def test_tenant_isolation_enforced_without_context(self, test_settings_with_auth):
        """ValueError raised when tenant isolation enforced but no org_id in context."""
        user_id = uuid4()

        # enforce_tenant_isolation=True but no request context
        with pytest.raises(ValueError, match="Tenant isolation is enforced"):
            build_cache_key("user", user_id)

    def test_explicit_global_tenant(self, test_settings):
        """Explicit global tenant bypasses auto-detection."""
        user_id = uuid4()
        key = build_cache_key("health", user_id, tenant_id="global")

        assert ":tenant-global:" in key
