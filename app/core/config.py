from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "fastapi-template"
    environment: str = "local"
    log_level: str = "debug"
    database_url: str = Field(
        default="postgresql+asyncpg://app:app@localhost:5432/app",
        alias="DATABASE_URL",
    )
    sqlalchemy_echo: bool = False
    enable_metrics: bool = True
    pagination_page_size: int = 50
    pagination_page_size_max: int = 200
    pagination_page_class: str | None = None


settings = Settings()
