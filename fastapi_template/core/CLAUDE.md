# Core Infrastructure

Configuration, middleware, auth, and cross-cutting concerns.

## PEP 563 Warning

**NEVER use `from __future__ import annotations` in this module.** Auth dependency definitions use `Annotated[..., Depends(...)]` which FastAPI evaluates at runtime. PEP 563 converts these to strings, breaking dependency injection.

Files that must NOT use PEP 563:
- `auth.py` (defines `CurrentUserFromHeaders`, `CurrentUserDep`)
- `tenants.py` (defines `TenantDep`)
- `permissions.py` (defines `RequireOwner`, `RequireAdmin`, `RequireMember`)

## Configuration (`config.py`)

```python
class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    environment: str = Field(alias="ENVIRONMENT", default="development")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

- Inherits `BaseSettings` from `pydantic_settings`
- All env vars via `Field(alias="ENV_VAR_NAME")`
- Validation: `@field_validator` methods, raises `ConfigurationError(ValueError)` on errors
- Provider enums use `StrEnum`
- Computed properties cached via `PrivateAttr(default=None)`

## Auth Dependencies

```python
# Required auth - raises 401 if headers missing
current_user: CurrentUserFromHeaders

# Optional auth - returns None if headers missing
current_user: OptionalUserFromHeaders
```

Both read from Oathkeeper-injected headers (`X-User-ID`, `X-Email`). The `CurrentUser` model is a `BaseModel` with `id: UUID`, `email: str`, `organization_id: UUID | None`.

## Middleware

```python
class MyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, setting: str) -> None:
        super().__init__(app)
        self.setting = setting

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        return response
```

- Constants at module level: `MAX_REQUEST_SIZE_BYTES_DEFAULT = 50 * 1024 * 1024`
- Logging threshold: `log_func = LOGGER.warning if response.status_code >= 400 else LOGGER.info`
- Auth middleware `public_paths` must include path prefixes for unauthenticated endpoints

## Logging

Module-level logger everywhere:

```python
LOGGER = logging.getLogger(__name__)
LOGGER.info("event_name", extra={"key": "value"})
```
