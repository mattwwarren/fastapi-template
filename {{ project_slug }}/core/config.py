"""Runtime configuration sourced from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
        default=True, description="Enable activity logging for audit trail"
    )
    activity_log_retention_days: int = Field(
        default=90, description="Number of days to retain activity logs before archival"
    )


settings = Settings()
