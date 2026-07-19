"""Cache key generation with multi-tenancy and versioning support.

Tenant scoping is threaded **explicitly**: callers pass either a
``TenantContext`` or a bare ``organization_id``. There is no ambient
request-context auto-detection and no runtime "missing tenant" error -- the
fail-closed guarantee comes from callers being unable to construct a
``TenantContext`` without verified organization membership, not from a check
inside this module. Genuinely global entries (health checks, system-wide data)
pass neither and land under the global sentinel namespace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi_template.core.config import settings

if TYPE_CHECKING:
    from fastapi_template.core.tenants import TenantContext

# Key-format constants (single source of truth; tests assert against these).
KEY_SEPARATOR = ":"
TENANT_PREFIX_FORMAT = "tenant-{}"
GLOBAL_TENANT_SENTINEL = "global"
DEFAULT_KEY_VERSION = "v1"


def build_cache_key(  # noqa: PLR0913 - multi-tenant key API: dual tenant inputs + versioning/suffix are all first-class
    resource_type: str,
    identifier: str | UUID,
    *,
    tenant: TenantContext | None = None,
    organization_id: UUID | str | None = None,
    version: str = DEFAULT_KEY_VERSION,
    suffix: str = "",
) -> str:
    """Build a hierarchical cache key with tenant isolation.

    Args:
        resource_type: Entity type (user, organization, document, ...).
        identifier: Unique identifier for the resource.
        tenant: Tenant context; its ``organization_id`` scopes the key.
        organization_id: Explicit organization id (used when no ``tenant``
            is supplied). ``tenant`` takes precedence when both are given.
        version: Cache schema version for invalidation (default: ``v1``).
        suffix: Optional suffix for key variations (e.g., ``with_orgs``).

    Returns:
        Cache key of the form
        ``{prefix}:tenant-{tenant}:{resource}:{id}:{version}[:{suffix}]``.

    Examples:
        # Global namespace (non-tenant-scoped)
        build_cache_key("health", "status")
        # "fastapi_template:tenant-global:health:status:v1"

        # Explicit tenant via organization_id
        build_cache_key("user", user_id, organization_id=org_id)
        # "fastapi_template:tenant-<org>:user:<user_id>:v1"
    """
    prefix = settings.cache_key_prefix or settings.app_name

    if tenant is not None:
        tenant_segment: str | UUID = tenant.organization_id
    elif organization_id is not None:
        tenant_segment = organization_id
    else:
        tenant_segment = GLOBAL_TENANT_SENTINEL

    parts = [
        prefix,
        TENANT_PREFIX_FORMAT.format(tenant_segment),
        resource_type,
        str(identifier),
        version,
    ]

    if suffix:
        parts.append(suffix)

    return KEY_SEPARATOR.join(parts)
