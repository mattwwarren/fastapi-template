"""Cache key generation with multi-tenancy and versioning support."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi_template.core.config import settings
from fastapi_template.core.logging import get_org_id

if TYPE_CHECKING:
    pass


def build_cache_key(
    resource_type: str,
    identifier: str | UUID,
    *,
    tenant_id: str | UUID | None = None,
    version: str = "v1",
    suffix: str = "",
) -> str:
    """Build hierarchical cache key with tenant isolation.

    Args:
        resource_type: Entity type (user, organization, document)
        identifier: Unique identifier for the resource
        tenant_id: Organization ID for multi-tenant isolation (auto-detected from context if None)
        version: Cache schema version for invalidation (default: v1)
        suffix: Optional suffix for variations (e.g., "with_orgs")

    Returns:
        Cache key: {prefix}:{tenant}:{resource}:{id}:{version}:{suffix}

    Examples:
        # Single-tenant (global namespace)
        build_cache_key("user", user_id)
        # "fastapi_template:tenant-global:user:uuid-123:v1"

        # Multi-tenant (explicit tenant ID)
        build_cache_key("organization", org_id, tenant_id=org_id)
        # "fastapi_template:tenant-org-456:organization:uuid-789:v1"

        # With suffix for variations
        build_cache_key("user", user_id, suffix="with_memberships")
        # "fastapi_template:tenant-global:user:uuid-123:v1:with_memberships"
    """
    prefix = settings.cache_key_prefix or settings.app_name

    # Auto-detect tenant from request context if enabled and not provided
    if tenant_id is None and settings.enforce_tenant_isolation:
        tenant_id = get_org_id()
        if tenant_id is None:
            # Tenant isolation is enforced but no tenant context found
            # This prevents cross-tenant cache leaks
            msg = (
                "Tenant isolation is enforced (ENFORCE_TENANT_ISOLATION=true) "
                "but no organization ID found in request context. "
                "Cache operations require tenant context."
            )
            raise ValueError(msg)
    else:
        tenant_id = tenant_id or "global"

    parts = [
        prefix,
        f"tenant-{tenant_id}",
        resource_type,
        str(identifier),
        version,
    ]

    if suffix:
        parts.append(suffix)

    return ":".join(parts)
