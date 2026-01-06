"""Object storage abstraction layer with multiple provider support.

This module provides a unified interface for storing and retrieving files across
different storage backends (local filesystem, Azure Blob Storage, AWS S3, Google Cloud Storage).

Architecture:
    - StorageService: Abstract base protocol defining the storage interface
    - StorageProvider: Enum of available storage backends
    - get_storage_service(): Factory function to instantiate the configured provider

Usage:
    from {{ project_slug }}.core.storage import get_storage_service

    storage = get_storage_service()
    storage_url = await storage.upload(
        document_id=doc_id,
        file_data=file_bytes,
        content_type="application/pdf"
    )

Provider Configuration:
    Set STORAGE_PROVIDER environment variable to choose backend:
    - "local" (default): Store files in local filesystem (development)
    - "azure": Azure Blob Storage (requires azure-storage-blob)
    - "aws_s3": AWS S3 (requires aioboto3)
    - "gcs": Google Cloud Storage (requires google-cloud-storage)

    See core/config.py for provider-specific configuration options.

Migration Path:
    To migrate from local to cloud storage:
    1. Update STORAGE_PROVIDER in .env
    2. Configure provider-specific settings (container/bucket names, credentials)
    3. Install optional dependencies: pip install .[azure] or .[aws] or .[gcs]
    4. Restart application - new uploads use cloud storage
    5. Migrate existing files using a data migration script
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol
from uuid import UUID


class StorageProvider(StrEnum):
    """Storage backend provider types.

    Attributes:
        LOCAL: Local filesystem storage (for development/testing)
        AZURE: Azure Blob Storage (production cloud storage)
        AWS_S3: AWS S3 (production cloud storage)
        GCS: Google Cloud Storage (production cloud storage)
    """

    LOCAL = "local"
    AZURE = "azure"
    AWS_S3 = "aws_s3"
    GCS = "gcs"


class StorageService(Protocol):
    """Abstract interface for file storage operations.

    All storage providers must implement these methods to ensure consistent
    behavior across different backends.

    Example implementation:
        class MyStorageService:
            async def upload(
                self,
                document_id: UUID,
                file_data: bytes,
                content_type: str,
                organization_id: UUID | None = None,
            ) -> str:
                # Upload logic here
                return storage_url
    """

    async def upload(
        self,
        document_id: UUID,
        file_data: bytes,
        content_type: str,
        organization_id: UUID | None = None,
    ) -> str:
        """Upload a file to storage.

        Args:
            document_id: Unique identifier for the document
            file_data: Binary file content
            content_type: MIME type (e.g., "application/pdf", "image/png")
            organization_id: Optional organization ID for multi-tenant isolation

        Returns:
            Storage URL or path where the file can be accessed

        Raises:
            StorageError: If upload fails due to network, permissions, or quota issues
        """
        ...

    async def download(self, document_id: UUID, organization_id: UUID | None = None) -> bytes | None:
        """Download a file from storage.

        Args:
            document_id: Unique identifier for the document
            organization_id: Optional organization ID for multi-tenant isolation

        Returns:
            Binary file content, or None if file not found

        Raises:
            StorageError: If download fails due to network or permissions issues
        """
        ...

    async def delete(self, document_id: UUID, organization_id: UUID | None = None) -> bool:
        """Delete a file from storage.

        Args:
            document_id: Unique identifier for the document
            organization_id: Optional organization ID for multi-tenant isolation

        Returns:
            True if file was deleted, False if file didn't exist

        Raises:
            StorageError: If deletion fails due to network or permissions issues
        """
        ...

    async def get_download_url(
        self,
        document_id: UUID,
        organization_id: UUID | None = None,
        expiry_seconds: int = 3600,
    ) -> str:
        """Generate a signed URL for direct file download.

        Args:
            document_id: Unique identifier for the document
            organization_id: Optional organization ID for multi-tenant isolation
            expiry_seconds: URL validity duration in seconds (default: 1 hour)

        Returns:
            Signed URL for direct download (cloud) or local path (filesystem)

        Raises:
            StorageError: If URL generation fails
        """
        ...


class StorageError(Exception):
    """Base exception for storage operations.

    Raised when storage operations fail due to network issues, permission problems,
    quota limits, or other provider-specific errors.

    Example:
        try:
            await storage.upload(doc_id, file_data, "application/pdf")
        except StorageError as e:
            logger.error(f"Failed to upload document: {e}")
            raise HTTPException(status_code=503, detail="Storage service unavailable")
    """

    pass


def get_storage_service() -> StorageService:
    """Factory function to create the configured storage service.

    Returns the appropriate storage service implementation based on
    STORAGE_PROVIDER environment variable.

    Returns:
        Configured StorageService instance

    Raises:
        ValueError: If STORAGE_PROVIDER is not recognized or required
                   dependencies are missing

    Example:
        storage = get_storage_service()
        url = await storage.upload(doc_id, file_bytes, "image/png")
    """
    from {{ project_slug }}.core.config import settings

    if settings.storage_provider == StorageProvider.LOCAL:
        from {{ project_slug }}.core.storage_providers import LocalStorageService

        return LocalStorageService(base_path=settings.storage_local_path)

    if settings.storage_provider == StorageProvider.AZURE:
        try:
            from {{ project_slug }}.core.storage_providers import AzureBlobStorageService
        except ImportError as e:
            missing_dependency_error = (
                "Azure Blob Storage requires 'azure-storage-blob' package. "
                "Install with: pip install .[azure]"
            )
            raise ValueError(missing_dependency_error) from e

        if not settings.storage_azure_container or not settings.storage_azure_connection_string:
            config_missing_error = (
                "Azure storage requires STORAGE_AZURE_CONTAINER and "
                "STORAGE_AZURE_CONNECTION_STRING environment variables"
            )
            raise ValueError(config_missing_error)

        return AzureBlobStorageService(
            container_name=settings.storage_azure_container,
            connection_string=settings.storage_azure_connection_string,
        )

    if settings.storage_provider == StorageProvider.AWS_S3:
        try:
            from {{ project_slug }}.core.storage_providers import S3StorageService
        except ImportError as e:
            missing_dependency_error = (
                "AWS S3 requires 'aioboto3' package. "
                "Install with: pip install .[aws]"
            )
            raise ValueError(missing_dependency_error) from e

        if not settings.storage_aws_bucket or not settings.storage_aws_region:
            config_missing_error = (
                "AWS S3 storage requires STORAGE_AWS_BUCKET and "
                "STORAGE_AWS_REGION environment variables"
            )
            raise ValueError(config_missing_error)

        return S3StorageService(
            bucket_name=settings.storage_aws_bucket,
            region=settings.storage_aws_region,
        )

    if settings.storage_provider == StorageProvider.GCS:
        try:
            from {{ project_slug }}.core.storage_providers import GCSStorageService
        except ImportError as e:
            missing_dependency_error = (
                "Google Cloud Storage requires 'google-cloud-storage' package. "
                "Install with: pip install .[gcs]"
            )
            raise ValueError(missing_dependency_error) from e

        if not settings.storage_gcs_bucket or not settings.storage_gcs_project_id:
            config_missing_error = (
                "GCS storage requires STORAGE_GCS_BUCKET and "
                "STORAGE_GCS_PROJECT_ID environment variables"
            )
            raise ValueError(config_missing_error)

        return GCSStorageService(
            bucket_name=settings.storage_gcs_bucket,
            project_id=settings.storage_gcs_project_id,
        )

    unrecognized_provider_error = (
        f"Unrecognized storage provider: {settings.storage_provider}. "
        f"Must be one of: {', '.join(StorageProvider)}"
    )
    raise ValueError(unrecognized_provider_error)
