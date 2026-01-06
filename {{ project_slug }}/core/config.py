"""Runtime configuration sourced from environment variables."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from {{ project_slug }}.core.storage import StorageProvider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "{{ project_slug }}"
    environment: str = "local"
    log_level: str = Field(default="debug", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://app:app@localhost:5432/app",
        alias="DATABASE_URL",
    )
    sqlalchemy_echo: bool = Field(default=False, alias="SQLALCHEMY_ECHO")
    enable_metrics: bool = Field(default=True, alias="ENABLE_METRICS")
    pagination_page_size: int = 50
    pagination_page_size_max: int = 200
    pagination_page_class: str | None = None
    activity_logging_enabled: bool = Field(
        default=True,
        alias="ACTIVITY_LOGGING_ENABLED",
        description="Enable activity logging for audit trail",
    )
    activity_log_retention_days: int = Field(
        default=90,
        alias="ACTIVITY_LOG_RETENTION_DAYS",
        description="Number of days to retain activity logs before archival",
    )
    max_file_size_bytes: int = Field(
        default=50 * 1024 * 1024,
        alias="MAX_FILE_SIZE_BYTES",
        description="Maximum file size for document uploads in bytes (default: 50MB)",
    )
    auth_provider_type: str = Field(
        default="none",
        alias="AUTH_PROVIDER_TYPE",
        description="Authentication provider (none, ory, auth0, keycloak, cognito)",
    )
    auth_provider_url: str | None = Field(
        default=None,
        alias="AUTH_PROVIDER_URL",
        description="Base URL for authentication provider (for token introspection)",
    )
    auth_provider_issuer: str | None = Field(
        default=None,
        alias="AUTH_PROVIDER_ISSUER",
        description="Expected token issuer (iss claim) for JWT validation",
    )
    jwt_algorithm: str = Field(
        default="RS256",
        alias="JWT_ALGORITHM",
        description="JWT algorithm for token validation (RS256, HS256, etc.)",
    )
    jwt_public_key: str | None = Field(
        default=None,
        alias="JWT_PUBLIC_KEY",
        description="Public key for JWT validation (PEM format) or path to key file",
    )
    _cors_allowed_origins_raw: str | list[str] = Field(
        default="http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
        description="List of allowed CORS origins (comma-separated string or list)",
    )
    _cors_allowed_origins_cache: list[str] | None = None
    enforce_tenant_isolation: bool = Field(
        default=True,
        alias="ENFORCE_TENANT_ISOLATION",
        description=(
            "Enforce tenant isolation for multi-tenant applications. "
            "When True, all endpoints (except public paths) require tenant context. "
            "Disable only for single-tenant deployments or public APIs. "
            "WARNING: Disabling this in a multi-tenant environment creates "
            "severe data leak vulnerabilities."
        ),
    )

    # Logging configuration
    request_id_header: str = Field(
        default="x-request-id",
        alias="REQUEST_ID_HEADER",
        description="HTTP header name for request correlation ID",
    )
    include_request_context_in_logs: bool = Field(
        default=True,
        alias="INCLUDE_REQUEST_CONTEXT_IN_LOGS",
        description="Enable automatic request context logging (user_id, org_id, "
        "request_id)",
    )

    # Storage configuration
    storage_provider: StorageProvider = Field(
        default=StorageProvider.LOCAL,
        alias="STORAGE_PROVIDER",
        description="Storage backend (local, azure, aws_s3, gcs)",
    )
    storage_local_path: str = Field(
        default="./uploads",
        alias="STORAGE_LOCAL_PATH",
        description="Local filesystem storage directory (used when provider=local)",
    )

    # Azure Blob Storage configuration
    storage_azure_container: str | None = Field(
        default=None,
        alias="STORAGE_AZURE_CONTAINER",
        description="Azure Blob Storage container name",
    )
    storage_azure_connection_string: str | None = Field(
        default=None,
        alias="STORAGE_AZURE_CONNECTION_STRING",
        description="Azure Storage account connection string",
    )

    # AWS S3 configuration
    storage_aws_bucket: str | None = Field(
        default=None,
        alias="STORAGE_AWS_BUCKET",
        description="AWS S3 bucket name",
    )
    storage_aws_region: str | None = Field(
        default=None,
        alias="STORAGE_AWS_REGION",
        description="AWS region (e.g., us-east-1, eu-west-1)",
    )

    # Google Cloud Storage configuration
    storage_gcs_bucket: str | None = Field(
        default=None,
        alias="STORAGE_GCS_BUCKET",
        description="Google Cloud Storage bucket name",
    )
    storage_gcs_project_id: str | None = Field(
        default=None,
        alias="STORAGE_GCS_PROJECT_ID",
        description="Google Cloud project ID",
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Get parsed list of allowed CORS origins.

        Parses comma-separated string from environment variable into list.
        Results are cached to avoid re-parsing on every access.

        Returns:
            List of allowed CORS origins (e.g., ["http://localhost:3000"])

        Examples:
            # From comma-separated string
            Settings(CORS_ALLOWED_ORIGINS="http://localhost:3000,http://localhost:3001")
            .cors_allowed_origins
            # ["http://localhost:3000", "http://localhost:3001"]

            # From list
            Settings(CORS_ALLOWED_ORIGINS=["http://localhost:3000"])
            .cors_allowed_origins
            # ["http://localhost:3000"]
        """
        # Return cached value if available
        if self._cors_allowed_origins_cache is not None:
            return self._cors_allowed_origins_cache

        # Parse raw value (either string or list)
        if isinstance(self._cors_allowed_origins_raw, str):
            parsed = [
                origin.strip()
                for origin in self._cors_allowed_origins_raw.split(",")
                if origin.strip()
            ]
        else:
            parsed = self._cors_allowed_origins_raw

        # Cache the result
        self._cors_allowed_origins_cache = parsed
        return parsed


settings = Settings()
