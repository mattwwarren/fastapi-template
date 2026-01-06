"""Tests for optional storage provider dependencies.

This module verifies that:
1. Local storage works without additional dependencies
2. Cloud storage providers (Azure, AWS, GCS) provide helpful error messages
   when required packages are missing
3. Configuration validation prevents misconfiguration
4. Factory function instantiates correct provider based on settings

Cloud provider tests use mocking to avoid requiring actual packages.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from {{ project_slug }}.core.config import Settings
from {{ project_slug }}.core.storage import (
    StorageProvider,
    get_storage_service,
)


class TestLocalStorageProvider:
    """Test local filesystem storage provider (always available)."""

    def test_local_storage_instantiation(self, test_settings_factory: Callable[..., Settings]) -> None:
        """Local storage should instantiate without additional dependencies."""
        settings = test_settings_factory(storage_provider=StorageProvider.LOCAL)
        with patch("{{ project_slug }}.core.storage.settings", settings):
            storage = get_storage_service()
            assert storage is not None
            # Verify it's actually a local storage service
            assert hasattr(storage, "upload")
            assert hasattr(storage, "download")
            assert hasattr(storage, "delete")

    def test_local_storage_with_custom_path(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Local storage should accept custom path configuration."""
        custom_path = "/custom/storage/path"
        settings = test_settings_factory(
            storage_provider=StorageProvider.LOCAL,
            storage_local_path=custom_path,
        )
        with patch("{{ project_slug }}.core.storage.settings", settings):
            storage = get_storage_service()
            assert storage is not None
            # Verify base_path is set correctly
            assert storage.base_path == custom_path  # type: ignore[attr-defined]


class TestAzureStorageProvider:
    """Test Azure Blob Storage provider with optional dependency handling."""

    def test_azure_storage_missing_dependency(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise helpful error when azure-storage-blob is not installed."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.AZURE,
            storage_azure_container="test-container",
            storage_azure_connection_string="test-connection",
        )

        # Mock ImportError to simulate missing azure-storage-blob
        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "AzureBlobStorageService" in str(name):
                raise ImportError("No module named 'azure.storage.blob'")
            return __import__(name, *args, **kwargs)

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ValueError, match="azure-storage-blob"):
                    get_storage_service()

    def test_azure_storage_missing_configuration(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error when Azure configuration is incomplete."""
        # Missing connection string
        settings = test_settings_factory(
            storage_provider=StorageProvider.AZURE,
            storage_azure_container="test-container",
            storage_azure_connection_string=None,
        )

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="STORAGE_AZURE_CONTAINER"):
                get_storage_service()

    def test_azure_storage_missing_container(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error when container name is missing."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.AZURE,
            storage_azure_container=None,
            storage_azure_connection_string="test-connection",
        )

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="STORAGE_AZURE"):
                get_storage_service()


class TestAWSS3StorageProvider:
    """Test AWS S3 provider with optional dependency handling."""

    def test_s3_storage_missing_dependency(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise helpful error when aioboto3 is not installed."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.AWS_S3,
            storage_aws_bucket="test-bucket",
            storage_aws_region="us-east-1",
        )

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "S3StorageService" in str(name):
                raise ImportError("No module named 'aioboto3'")
            return __import__(name, *args, **kwargs)

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ValueError, match="aioboto3"):
                    get_storage_service()

    def test_s3_storage_missing_bucket(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error when S3 bucket name is missing."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.AWS_S3,
            storage_aws_bucket=None,
            storage_aws_region="us-east-1",
        )

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="STORAGE_AWS"):
                get_storage_service()

    def test_s3_storage_missing_region(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error when AWS region is missing."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.AWS_S3,
            storage_aws_bucket="test-bucket",
            storage_aws_region=None,
        )

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="STORAGE_AWS"):
                get_storage_service()


class TestGCSStorageProvider:
    """Test Google Cloud Storage provider with optional dependency handling."""

    def test_gcs_storage_missing_dependency(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise helpful error when google-cloud-storage is not installed."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.GCS,
            storage_gcs_bucket="test-bucket",
            storage_gcs_project_id="test-project",
        )

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "GCSStorageService" in str(name):
                raise ImportError("No module named 'google.cloud.storage'")
            return __import__(name, *args, **kwargs)

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ValueError, match="google-cloud-storage"):
                    get_storage_service()

    def test_gcs_storage_missing_bucket(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error when GCS bucket name is missing."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.GCS,
            storage_gcs_bucket=None,
            storage_gcs_project_id="test-project",
        )

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="STORAGE_GCS"):
                get_storage_service()

    def test_gcs_storage_missing_project_id(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error when GCS project ID is missing."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.GCS,
            storage_gcs_bucket="test-bucket",
            storage_gcs_project_id=None,
        )

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="STORAGE_GCS"):
                get_storage_service()


class TestStorageProviderFactory:
    """Test factory function behavior with different configurations."""

    def test_factory_invalid_provider(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Should raise error for unrecognized provider."""
        settings = test_settings_factory(storage_provider="invalid_provider")  # type: ignore[arg-type]

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with pytest.raises(ValueError, match="Unrecognized storage provider"):
                get_storage_service()

    def test_factory_returns_correct_provider_local(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Factory should return local storage service for LOCAL provider."""
        settings = test_settings_factory(storage_provider=StorageProvider.LOCAL)

        with patch("{{ project_slug }}.core.storage.settings", settings):
            storage = get_storage_service()
            assert storage is not None
            # Verify it's the local storage service by checking base_path
            assert hasattr(storage, "base_path")

    def test_error_messages_include_installation_instructions(
        self, test_settings_factory: Callable[..., Settings]
    ) -> None:
        """Error messages should include pip install instructions."""
        settings = test_settings_factory(
            storage_provider=StorageProvider.AZURE,
            storage_azure_container="container",
            storage_azure_connection_string="string",
        )

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "AzureBlobStorageService" in str(name):
                raise ImportError("No module named 'azure'")
            return __import__(name, *args, **kwargs)

        with patch("{{ project_slug }}.core.storage.settings", settings):
            with patch("builtins.__import__", side_effect=mock_import):
                with pytest.raises(ValueError) as exc_info:
                    get_storage_service()
                # Verify error message includes installation instruction
                assert "pip install" in str(exc_info.value)
                assert "[azure]" in str(exc_info.value)


class TestStorageProviderEnum:
    """Test StorageProvider enum values and behavior."""

    def test_provider_enum_values(self) -> None:
        """Verify all expected provider types are available."""
        expected_providers = {"local", "azure", "aws_s3", "gcs"}
        actual_providers = {p.value for p in StorageProvider}
        assert actual_providers == expected_providers

    def test_provider_string_representation(self) -> None:
        """Verify provider values match configuration strings."""
        assert StorageProvider.LOCAL.value == "local"
        assert StorageProvider.AZURE.value == "azure"
        assert StorageProvider.AWS_S3.value == "aws_s3"
        assert StorageProvider.GCS.value == "gcs"
