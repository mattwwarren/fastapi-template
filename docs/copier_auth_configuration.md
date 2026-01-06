# Copier Auth Provider Configuration

Guide for configuring authentication providers during FastAPI template generation with Copier.

## Overview

Copier allows users to select their preferred auth provider when generating a new project. This document explains the design and implementation.

## Current Configuration

The `copier.yaml` file contains questions for project generation. Auth provider selection should be added.

### Proposed Copier Configuration

```yaml
# copier.yaml

_envops:
  autoescape: true
  block_end_string: "-%}"
  block_start_string: "{%"
  comment_end_string: "#}"
  comment_start_string: "{#"
  keep_trailing_newline: true
  variable_end_string: "}}"
  variable_start_string: "{{"

_skip_if:
  - "{% if not include_auth %}"

questions:
  project_name:
    type: str
    help: Project name
    default: My Project

  project_slug:
    type: str
    help: Project slug (lowercase, no spaces)
    default: "{{ project_name.lower().replace(' ', '_') }}"

  # NEW: Authentication provider selection
  use_authentication:
    type: bool
    help: Include authentication support?
    default: true

  auth_provider:
    type: str
    help: |
      Authentication provider:
      - none: No authentication (public API)
      - ory: Ory (open source, self-hosted)
      - auth0: Auth0 (commercial SaaS)
      - keycloak: Keycloak (open source)
      - cognito: AWS Cognito (AWS managed)
    default: ory
    when: "{{ use_authentication }}"
    choices:
      - none
      - ory
      - auth0
      - keycloak
      - cognito

  auth_provider_url:
    type: str
    help: |
      Auth provider base URL
      Examples:
      - Ory: https://your-project.ory.sh
      - Auth0: https://your-tenant.auth0.com
      - Keycloak: https://your-keycloak.example.com/auth
      - Cognito: https://cognito-idp.region.amazonaws.com/region_code
    when: "{{ auth_provider != 'none' and use_authentication }}"

  auth_provider_issuer:
    type: str
    help: |
      Expected token issuer (iss claim)
      Usually same as auth provider URL
    when: "{{ auth_provider != 'none' and use_authentication }}"

  jwt_algorithm:
    type: str
    help: |
      JWT algorithm for token validation:
      - RS256: RSA (recommended)
      - HS256: HMAC
    default: RS256
    choices:
      - RS256
      - HS256
    when: "{{ auth_provider != 'none' and use_authentication }}"

  jwt_public_key:
    type: str
    help: |
      (Optional) JWT public key for local validation
      Leave empty to always call auth provider
    when: "{{ auth_provider != 'none' and use_authentication }}"

  include_multi_tenancy:
    type: bool
    help: Include multi-tenant support (organizations)?
    default: true

  # ... other questions ...
```

## Template Customization

Based on auth provider selection, templates adjust configuration:

### .env Template

```bash
# .env.example

# Auth Configuration
AUTH_PROVIDER_TYPE={{ auth_provider }}
{% if auth_provider != 'none' %}
AUTH_PROVIDER_URL={{ auth_provider_url }}
AUTH_PROVIDER_ISSUER={{ auth_provider_issuer }}
JWT_ALGORITHM={{ jwt_algorithm }}
{% if jwt_public_key %}
JWT_PUBLIC_KEY=<your-public-key>
{% endif %}
{% endif %}
```

### pyproject.toml Conditional Dependencies

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

### Core Auth Configuration

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

### Auth Middleware Configuration

```python
# {{ project_slug }}/main.py

from {{ project_slug }}.core.config import settings
from {{ project_slug }}.core.auth import AuthMiddleware

app = FastAPI()

{% if auth_provider != 'none' %}
# Add authentication middleware
app.add_middleware(AuthMiddleware)

# Auth provider specific setup
{% if auth_provider == 'ory' %}
# Ory setup
from {{ project_slug }}.core.auth_providers import OryProvider
auth_provider = OryProvider(settings.auth_provider_url)

{% elif auth_provider == 'auth0' %}
# Auth0 setup
from {{ project_slug }}.core.auth_providers import Auth0Provider
auth_provider = Auth0Provider(
    domain=settings.auth_provider_url,
    audience=settings.auth_provider_issuer,
)

{% elif auth_provider == 'keycloak' %}
# Keycloak setup
from {{ project_slug }}.core.auth_providers import KeycloakProvider
auth_provider = KeycloakProvider(
    server_url=settings.auth_provider_url,
    realm=settings.keycloak_realm,
)

{% elif auth_provider == 'cognito' %}
# Cognito setup
from {{ project_slug }}.core.auth_providers import CognitoProvider
auth_provider = CognitoProvider(
    region=settings.cognito_region,
    user_pool_id=settings.cognito_user_pool_id,
)
{% endif %}

{% else %}
# No authentication - all endpoints public
{% endif %}
```

### Test Configuration

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
? Include authentication? [Y/n] Y
? Auth provider:
  > ory
    auth0
    keycloak
    cognito
    none
? Auth provider URL: https://my-project.ory.sh
? Token issuer: https://my-project.ory.sh
? JWT algorithm: [RS256/HS256] RS256
? Include multi-tenancy? [Y/n] Y

✓ Generated project with Ory authentication
✓ See docs/auth_providers/ory_setup.md for next steps
```

### Post-Generation

After generation:

```
cd my-project
# 1. Follow provider-specific guide
cat docs/auth_providers/ory_setup.md

# 2. Update .env with provider credentials
nano .env

# 3. Run tests to verify setup
pytest tests/

# 4. Start development
uvicorn main:app --reload
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
