"""Settings fixtures for testing with isolated configuration.

This module provides factory fixtures that create fresh Settings instances
for each test, ensuring pytest-xdist compatibility by avoiding global state
mutation.

Pattern:
    - test_settings_factory: Creates Settings with custom overrides
    - test_settings: Default factory with standard test database URL
    - test_settings_with_auth: Factory pre-configured for auth testing

Each fixture returns a fresh Settings instance (not the global singleton),
allowing tests to run in parallel without interference.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi_template_test.core.config import Settings
from fastapi_template_test.core.storage import StorageProvider
from pydantic import ValidationError


@pytest.fixture
def test_settings_factory() -> Callable[..., Settings]:
    """Factory for creating isolated Settings instances.

    Returns a callable that creates fresh Settings with custom overrides.
    Use this to create multiple Settings instances in a single test.

    Usage:
        def test_multiple_configs(test_settings_factory):
            settings_1 = test_settings_factory(environment="staging")
            settings_2 = test_settings_factory(environment="production")
            assert settings_1.environment != settings_2.environment

    Returns:
        Callable that accepts keyword arguments for Settings fields
    """

    def _factory(**overrides: dict) -> Settings:
        # Get a base Settings instance to read current defaults
        base_settings = Settings(_env_file=None)

        # Build field dictionary with test defaults and current values
        fields = {
            "database_url": "postgresql+asyncpg://app:app@localhost:5432/app_test",
            "environment": "test",
            "log_level": "debug",
            "activity_logging_enabled": True,
            "auth_provider_type": "none",
            # Include all other fields from base to ensure complete coverage
            "app_name": base_settings.app_name,
            "sqlalchemy_echo": base_settings.sqlalchemy_echo,
            "enable_metrics": base_settings.enable_metrics,
            "pagination_page_size": base_settings.pagination_page_size,
            "pagination_page_size_max": base_settings.pagination_page_size_max,
            "pagination_page_class": base_settings.pagination_page_class,
            "activity_log_retention_days": base_settings.activity_log_retention_days,
            "max_file_size_bytes": base_settings.max_file_size_bytes,
            "auth_provider_url": base_settings.auth_provider_url,
            "auth_provider_issuer": base_settings.auth_provider_issuer,
            "jwt_algorithm": base_settings.jwt_algorithm,
            "jwt_public_key": base_settings.jwt_public_key,
            "cors_allowed_origins_raw": base_settings.cors_allowed_origins_raw,
            "enforce_tenant_isolation": base_settings.enforce_tenant_isolation,
            "request_id_header": base_settings.request_id_header,
            "include_request_context_in_logs": base_settings.include_request_context_in_logs,
            "storage_provider": base_settings.storage_provider,
            "storage_local_path": base_settings.storage_local_path,
            "storage_azure_container": base_settings.storage_azure_container,
            "storage_azure_connection_string": base_settings.storage_azure_connection_string,
            "storage_aws_bucket": base_settings.storage_aws_bucket,
            "storage_aws_region": base_settings.storage_aws_region,
            "storage_gcs_bucket": base_settings.storage_gcs_bucket,
            "storage_gcs_project_id": base_settings.storage_gcs_project_id,
        }

        # Apply overrides
        fields.update(overrides)

        # Validate enum fields before construction
        # storage_provider must be a valid StorageProvider enum
        if "storage_provider" in overrides:
            provider = overrides["storage_provider"]
            if isinstance(provider, str):
                # Validate enum value and raise ValidationError if invalid
                try:
                    fields["storage_provider"] = StorageProvider(provider)
                except ValueError as err:
                    error_msg = str(err)
                    # Raise ValidationError matching Pydantic's format
                    raise ValidationError.from_exception_data(
                        "Settings",
                        [
                            {
                                "type": "enum",
                                "loc": ("storage_provider",),
                                "msg": error_msg,
                                "input": provider,
                                "ctx": {"expected": "a valid StorageProvider"},
                            }
                        ],
                    ) from err

        # NOTE: BaseSettings has extra='forbid' which prevents normal instantiation with kwargs.
        # Use model_construct() to bypass BaseSettings' validation while still building a valid instance.
        return Settings.model_construct(**fields)

    return _factory


@pytest.fixture
def test_settings(test_settings_factory: Callable[..., Settings]) -> Settings:
    """Fresh Settings instance for testing.

    Creates an isolated Settings instance using default test configuration.
    Each test gets a fresh instance, supporting pytest-xdist parallel execution.

    Usage:
        def test_pagination(test_settings):
            assert test_settings.pagination_page_size == 50
            assert test_settings.pagination_page_size_max == 200

    Returns:
        Fresh Settings instance with test database URL
    """
    return test_settings_factory()


@pytest.fixture
def test_settings_with_auth(test_settings_factory: Callable[..., Settings]) -> Settings:
    """Settings configured for authentication testing.

    Pre-configures settings with a test auth provider setup.

    Usage:
        def test_auth_enabled(test_settings_with_auth):
            assert test_settings_with_auth.auth_provider_type == "ory"
            assert test_settings_with_auth.auth_provider_url is not None

    Returns:
        Fresh Settings instance with auth provider configured
    """
    return test_settings_factory(
        auth_provider_type="ory",
        auth_provider_url="https://test-ory.example.com",
        auth_provider_issuer="https://test-ory.example.com",
    )


@pytest.fixture
def test_settings_with_storage(test_settings_factory: Callable[..., Settings]) -> Settings:
    """Settings configured for cloud storage testing.

    Pre-configures settings with Azure Blob Storage for testing.

    Returns:
        Fresh Settings instance with Azure storage configured
    """
    from fastapi_template_test.core.storage import StorageProvider

    return test_settings_factory(
        storage_provider=StorageProvider.AZURE,
        storage_azure_container="test-container",
        storage_azure_connection_string="DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=testkey;EndpointSuffix=core.windows.net",
    )


@pytest.fixture
def test_settings_with_activity_logging_disabled(
    test_settings_factory: Callable[..., Settings],
) -> Settings:
    """Settings with activity logging disabled.

    Useful for testing that activity logging integration doesn't interfere
    with core functionality when disabled.

    Returns:
        Fresh Settings instance with activity logging disabled
    """
    return test_settings_factory(activity_logging_enabled=False)
