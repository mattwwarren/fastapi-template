# Copier Auth Provider Configuration

Guide for configuring authentication providers during FastAPI template generation with Copier.

## Overview

Copier allows users to select their preferred auth provider when generating a new project. This document explains the implementation.

## Implementation

The `copier.yaml` file contains questions for project generation, including authentication provider selection.

### Copier Configuration

```yaml
# copier.yaml (excerpt showing auth configuration)

auth_enabled:
  type: bool
  help: "Enable authentication middleware? (Requires auth provider configuration)"
  default: false

auth_provider:
  type: str
  help: |
    Authentication provider:
      - none: No authentication (public API)
      - ory: Ory (open source, self-hosted)
      - auth0: Auth0 (commercial SaaS)
      - keycloak: Keycloak (open source)
      - cognito: AWS Cognito (AWS managed)
  default: none
  choices:
    - none
    - ory
    - auth0
    - keycloak
    - cognito
  when: "{{ auth_enabled }}"

multi_tenant:
  type: bool
  help: "Enable multi-tenant isolation? (Requires authentication)"
  default: true

storage_provider:
  type: str
  help: |
    Storage provider for file uploads:
      - local: Local filesystem (development)
      - s3: AWS S3 (production)
      - azure: Azure Blob Storage (production)
      - gcs: Google Cloud Storage (production)
  default: local
  choices:
    - local
    - s3
    - azure
    - gcs

cors_origins:
  type: str
  help: "CORS allowed origins (comma-separated, e.g., 'http://localhost:3000')"
  default: "http://localhost:3000"

enable_metrics:
  type: bool
  help: "Enable Prometheus metrics endpoint at /metrics?"
  default: true

enable_activity_logging:
  type: bool
  help: "Enable activity logging for audit trails?"
  default: true
```

## Template Customization

Based on configuration selections, templates adjust automatically using Jinja2 conditionals.

### .env Template

```bash
# .env.example

# Authentication (JWT)
# Authentication provider: {{ auth_provider if auth_enabled else 'none' }}
AUTH_PROVIDER_TYPE={{ auth_provider if auth_enabled else 'none' }}
{% if auth_enabled and auth_provider != 'none' -%}
AUTH_PROVIDER_URL=https://your-auth-provider.com
AUTH_PROVIDER_ISSUER=https://your-auth-provider.com/
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
{% else -%}
# AUTH_PROVIDER_URL=https://your-auth-provider.com
# AUTH_PROVIDER_ISSUER=https://your-auth-provider.com/
# JWT_ALGORITHM=RS256
# JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
{% endif -%}

# Tenant Isolation
ENFORCE_TENANT_ISOLATION={{ 'true' if multi_tenant else 'false' }}

# Storage Configuration
STORAGE_PROVIDER={{ storage_provider }}
{% if storage_provider == 'local' -%}
STORAGE_LOCAL_PATH=./uploads
{% elif storage_provider == 's3' -%}
STORAGE_AWS_BUCKET=my-document-bucket
STORAGE_AWS_REGION=us-east-1
{% elif storage_provider == 'azure' -%}
STORAGE_AZURE_CONTAINER=documents
STORAGE_AZURE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
{% elif storage_provider == 'gcs' -%}
STORAGE_GCS_BUCKET=my-document-bucket
STORAGE_GCS_PROJECT_ID=my-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
{% endif -%}

# CORS Configuration
CORS_ALLOWED_ORIGINS={{ cors_origins }}

# Observability
ENABLE_METRICS={{ 'true' if enable_metrics else 'false' }}
ACTIVITY_LOGGING_ENABLED={{ 'true' if enable_activity_logging else 'false' }}
```

### pyproject.toml Conditional Dependencies

{% raw %}
```toml
[project]
dependencies = [
  # Core dependencies
  "fastapi>=0.104",
  # ... other deps ...

  # Auth provider dependencies (conditional)
  {% if auth_provider == 'auth0' %}
  # Auth0 specific (if needed)
  {% elif auth_provider == 'cognito' %}
  "boto3>=1.26",
  {% endif %}
]

[project.optional-dependencies]
{% if auth_provider == 'ory' %}
ory = ["python-httpx>=0.23"]
{% elif auth_provider == 'auth0' %}
auth0 = ["python-httpx>=0.23"]
{% elif auth_provider == 'keycloak' %}
keycloak = ["python-keycloak>=3.0"]
{% elif auth_provider == 'cognito' %}
cognito = ["boto3>=1.26"]
{% endif %}
```
{% endraw %}

### Core Auth Configuration

{% raw %}
```python
# {{ project_slug }}/core/config.py

class Settings(BaseSettings):
    # ... existing fields ...

    auth_provider_type: str = Field(
        default="{{ auth_provider }}",
        alias="AUTH_PROVIDER_TYPE",
        description="Authentication provider",
    )

    auth_provider_url: str | None = Field(
        default="{% if auth_provider != 'none' %}{{ auth_provider_url }}{% endif %}",
        alias="AUTH_PROVIDER_URL",
    )

    auth_provider_issuer: str | None = Field(
        default="{% if auth_provider != 'none' %}{{ auth_provider_issuer }}{% endif %}",
        alias="AUTH_PROVIDER_ISSUER",
    )

    jwt_algorithm: str = Field(
        default="{{ jwt_algorithm }}",
        alias="JWT_ALGORITHM",
    )

    jwt_public_key: str | None = Field(
        default={% if jwt_public_key %}"{{ jwt_public_key }}"{% else %}None{% endif %},
        alias="JWT_PUBLIC_KEY",
    )
```
{% endraw %}

### Auth Middleware Configuration

```python
# {{ project_slug }}/main.py (excerpt)

{% if auth_enabled -%}
# Authentication Middleware
# JWT authentication for all endpoints (public endpoints excluded automatically)
from {{ project_slug }}.core.auth import AuthMiddleware

app.add_middleware(AuthMiddleware)
{% else -%}
# Authentication Middleware (DISABLED)
# To enable authentication:
#   1. Regenerate project with copier and set auth_enabled=true
#   2. Or manually uncomment the following and configure .env:
#
# from {{ project_slug }}.core.auth import AuthMiddleware
# app.add_middleware(AuthMiddleware)
{% endif -%}

{% if multi_tenant and auth_enabled -%}
# Tenant Isolation Middleware
# Enforces tenant isolation for all endpoints
from {{ project_slug }}.core.tenants import TenantIsolationMiddleware

app.add_middleware(TenantIsolationMiddleware)
{% elif multi_tenant and not auth_enabled -%}
# Tenant Isolation Middleware (DISABLED - Authentication Required)
# Multi-tenant isolation requires authentication to be enabled first.
{% else -%}
# Tenant Isolation Middleware (DISABLED - Single Tenant Mode)
{% endif -%}
```

### Test Configuration

{% raw %}
```python
# {{ project_slug }}/tests/conftest.py

{% if auth_provider != 'none' %}
from {{ project_slug }}.tests.mocks.auth_providers import (
    {% if auth_provider == 'ory' %}
    mock_ory_provider,
    {% elif auth_provider == 'auth0' %}
    mock_auth0_provider,
    {% elif auth_provider == 'keycloak' %}
    mock_keycloak_provider,
    {% elif auth_provider == 'cognito' %}
    mock_cognito_provider,
    {% endif %}
)

# Tests will use mocked auth provider
{% else %}
# No authentication - all requests allowed in tests
{% endif %}
```
{% endraw %}

## Provider-Specific Documentation

### Ory Setup

When user selects Ory:

1. **Required Steps**:
   - Create Ory project at https://console.ory.sh
   - Get project URL (e.g., https://my-project.ory.sh)
   - Set AUTH_PROVIDER_URL

2. **Automatic Configuration**:
   - JWT algorithm defaults to RS256
   - Issuer defaults to provider URL
   - Test fixtures provided

3. **Documentation Reference**:
   - `docs/auth_providers/ory_setup.md`

### Auth0 Setup

When user selects Auth0:

1. **Required Steps**:
   - Create Auth0 application at https://manage.auth0.com
   - Get domain and application ID
   - Create API

2. **Automatic Configuration**:
   - JWKS endpoint configured
   - Token introspection setup
   - Public key fetched automatically

3. **Documentation Reference**:
   - `docs/auth_providers/auth0_setup.md`

### Keycloak Setup

When user selects Keycloak:

1. **Required Steps**:
   - Self-host or use managed Keycloak
   - Create realm
   - Create client application

2. **Automatic Configuration**:
   - Token endpoint configured
   - Token validation setup
   - JWKS URL set up

3. **Documentation Reference**:
   - `docs/auth_providers/keycloak_setup.md`

### Cognito Setup

When user selects Cognito:

1. **Required Steps**:
   - Create AWS Cognito user pool
   - Create app client
   - Configure resource server

2. **Automatic Configuration**:
   - User pool ID extraction
   - JWKS URL setup
   - Token validation

3. **Documentation Reference**:
   - `docs/auth_providers/cognito_setup.md`

## Implementation Steps

### Step 1: Update copier.yaml

```bash
# Add auth provider questions to copier.yaml
```

### Step 2: Create Conditional Templates

```bash
# Create templated files:
# - main.py (conditional middleware)
# - .env.example (provider URL)
# - pyproject.toml (optional dependencies)
```

### Step 3: Create Setup Guides

```bash
# Create docs/auth_providers/:
# - ory_setup.md
# - auth0_setup.md
# - keycloak_setup.md
# - cognito_setup.md
# - none_setup.md (public API guide)
```

### Step 4: Create Provider Implementations

```bash
# Create conditional auth providers in core/auth_providers/:
# - ory.py
# - auth0.py
# - keycloak.py
# - cognito.py
```

### Step 5: Create Test Fixtures

Mock fixtures already exist in `tests/mocks/auth_providers.py`

## User Experience

### Generation Flow

```
copier copy <template-url> my-project
? Project name: My App
? Project slug (auto): my_app
? Brief project description: A FastAPI microservice
? Development server port: 8000
? Enable authentication middleware? [y/N] y
? Authentication provider:
  > ory
    auth0
    keycloak
    cognito
    none
? Enable multi-tenant isolation? [Y/n] Y
? Storage provider for file uploads:
  > local
    s3
    azure
    gcs
? CORS allowed origins: http://localhost:3000
? Enable Prometheus metrics endpoint at /metrics? [Y/n] Y
? Enable activity logging for audit trails? [Y/n] Y

Running post-generation tasks...
✓ Created .env from .env.example
✓ Dependencies installed successfully
⚠ Database migration skipped (configure DATABASE_URL first)

🎉 Project My App generated successfully!
```

### Post-Generation

After generation:

```bash
cd my-project

# 1. Configure database connection in .env
# Edit DATABASE_URL to point to your PostgreSQL instance

# 2. Run database migrations (if not done automatically)
uv run alembic upgrade head

# 3. Configure auth provider (if authentication enabled)
# Edit .env and set AUTH_PROVIDER_URL, AUTH_PROVIDER_ISSUER, JWT_PUBLIC_KEY

# 4. Start development server
uv run fastapi dev my_app/main.py

# 5. View API docs
open http://localhost:8000/docs

# 6. Run tests to verify setup
uv run pytest tests/ -v
```

## Advanced Configuration

### Custom Provider

For users with custom auth providers:

```python
# {{ project_slug }}/core/auth_providers/custom.py

from {{ project_slug }}.core.auth import AuthProvider

class CustomAuthProvider(AuthProvider):
    """Custom authentication provider implementation."""

    async def validate_token(self, token: str) -> dict:
        """Validate token with custom logic."""
        # Custom implementation
        pass
```

### Multiple Providers

For advanced users wanting to support multiple providers:

```python
# {{ project_slug }}/core/auth.py

PRIMARY_PROVIDER = get_provider(settings.auth_provider_type)
FALLBACK_PROVIDERS = [...]

async def validate_token(token: str) -> dict:
    """Try primary, fall back to alternatives."""
    try:
        return await PRIMARY_PROVIDER.validate_token(token)
    except Exception:
        for provider in FALLBACK_PROVIDERS:
            try:
                return await provider.validate_token(token)
            except Exception:
                continue
        raise
```

## Maintenance

### When Adding New Provider

1. Update `copier.yaml` with new provider choice
2. Create provider implementation in `core/auth_providers/`
3. Create mock in `tests/mocks/auth_providers.py`
4. Create setup guide in `docs/auth_providers/`
5. Update conditionals in templates
6. Add example configuration to `examples/`

### Testing Auth Providers

```bash
# Test Ory
pytest tests/test_auth_ory.py

# Test Auth0
pytest tests/test_auth_auth0.py

# Test Keycloak
pytest tests/test_auth_keycloak.py

# Test Cognito
pytest tests/test_auth_cognito.py

# Test all
pytest tests/test_auth_*.py
```

## See Also

- [Copier Documentation](https://copier.readthedocs.io/)
- [Auth Configuration](../core/auth.py) - Authentication implementation
- [Resilience Patterns](resilience_patterns.md) - Handle auth provider outages
- [Testing External Services](testing_external_services.md) - Mock auth providers in tests
