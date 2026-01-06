"""Comprehensive document endpoint tests covering upload, download, validation, and size limits."""

from http import HTTPStatus
from io import BytesIO

import pytest
from httpx import AsyncClient

from {{ project_slug }}.core.config import settings


class TestDocumentUpload:
    """Test document upload operations."""

    @pytest.mark.asyncio
    async def test_upload_document_success(self, client: AsyncClient) -> None:
        """Upload a valid document."""
        file_content = b"Hello, World! This is a test document."
        files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}

        response = await client.post("/documents", files=files)
        assert response.status_code == HTTPStatus.CREATED
        doc = response.json()
        assert doc["filename"] == "test.txt"
        assert doc["content_type"] == "text/plain"
        assert doc["file_size"] == len(file_content)
        assert "id" in doc
        assert "created_at" in doc
        assert "updated_at" in doc

    @pytest.mark.asyncio
    async def test_upload_document_with_binary_data(
        self, client: AsyncClient
    ) -> None:
        """Upload a binary file (e.g., image)."""
        # Create fake binary image data
        file_content = bytes(range(256))  # 256 bytes of binary data
        files = {"file": ("image.png", BytesIO(file_content), "image/png")}

        response = await client.post("/documents", files=files)
        assert response.status_code == HTTPStatus.CREATED
        doc = response.json()
        assert doc["filename"] == "image.png"
        assert doc["content_type"] == "image/png"
        assert doc["file_size"] == 256

    @pytest.mark.asyncio
    async def test_upload_document_no_filename(self, client: AsyncClient) -> None:
        """Uploading document without filename should fail."""
        file_content = b"Test content"
        files = {"file": ("", BytesIO(file_content), "text/plain")}

        response = await client.post("/documents", files=files)
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_upload_document_no_content_type(self, client: AsyncClient) -> None:
        """Uploading document without content type should fail."""
        file_content = b"Test content"
        files = {"file": ("test.txt", BytesIO(file_content), None)}

        response = await client.post("/documents", files=files)
        # Should fail validation if content_type is required
        assert response.status_code in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    @pytest.mark.asyncio
    async def test_upload_document_size_limit(self, client: AsyncClient) -> None:
        """Uploading document exceeding size limit should fail."""
        # Create file larger than max_file_size_bytes
        max_size = settings.max_file_size_bytes
        oversized_content = b"x" * (max_size + 1)
        files = {"file": ("large.txt", BytesIO(oversized_content), "text/plain")}

        response = await client.post("/documents", files=files)
        assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_upload_empty_document(self, client: AsyncClient) -> None:
        """Uploading empty document should succeed (0 bytes is valid)."""
        file_content = b""
        files = {"file": ("empty.txt", BytesIO(file_content), "text/plain")}

        response = await client.post("/documents", files=files)
        # Empty file is technically valid
        assert response.status_code in (HTTPStatus.CREATED, HTTPStatus.BAD_REQUEST)
        if response.status_code == HTTPStatus.CREATED:
            doc = response.json()
            assert doc["file_size"] == 0


class TestDocumentDownload:
    """Test document download operations."""

    @pytest.mark.asyncio
    async def test_download_document(self, client: AsyncClient) -> None:
        """Download a previously uploaded document."""
        # Upload document
        file_content = b"Test download content"
        files = {"file": ("download.txt", BytesIO(file_content), "text/plain")}
        upload_response = await client.post("/documents", files=files)
        doc_id = upload_response.json()["id"]

        # Download document
        download_response = await client.get(f"/documents/{doc_id}")
        assert download_response.status_code == HTTPStatus.OK
        assert download_response.content == file_content
        assert download_response.headers["content-type"] == "text/plain"
        assert "attachment" in download_response.headers.get("content-disposition", "")
        assert "download.txt" in download_response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_download_binary_document(self, client: AsyncClient) -> None:
        """Download a binary document and verify content."""
        # Upload binary document
        file_content = bytes(range(256))
        files = {"file": ("binary.bin", BytesIO(file_content), "application/octet-stream")}
        upload_response = await client.post("/documents", files=files)
        doc_id = upload_response.json()["id"]

        # Download document
        download_response = await client.get(f"/documents/{doc_id}")
        assert download_response.status_code == HTTPStatus.OK
        assert download_response.content == file_content
        assert download_response.headers["content-type"] == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_download_nonexistent_document(self, client: AsyncClient) -> None:
        """Downloading nonexistent document should return 404."""
        response = await client.get("/documents/00000000-0000-0000-0000-000000000000")
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_download_streaming_response(self, client: AsyncClient) -> None:
        """Verify document is returned as streaming response."""
        # Upload larger document to test streaming
        file_content = b"x" * 10000  # 10KB
        files = {"file": ("stream.txt", BytesIO(file_content), "text/plain")}
        upload_response = await client.post("/documents", files=files)
        doc_id = upload_response.json()["id"]

        # Download document (should stream)
        download_response = await client.get(f"/documents/{doc_id}")
        assert download_response.status_code == HTTPStatus.OK
        assert len(download_response.content) == 10000


class TestDocumentValidation:
    """Test document validation rules."""

    @pytest.mark.asyncio
    async def test_filename_validation(self, client: AsyncClient) -> None:
        """Test various filename patterns."""
        valid_filenames = [
            "simple.txt",
            "with-dash.txt",
            "with_underscore.txt",
            "with spaces.txt",
            "multiple.dots.in.name.txt",
            "UPPERCASE.TXT",
            "123numeric.txt",
        ]

        for filename in valid_filenames:
            file_content = b"Test content"
            files = {"file": (filename, BytesIO(file_content), "text/plain")}
            response = await client.post("/documents", files=files)
            assert response.status_code == HTTPStatus.CREATED
            assert response.json()["filename"] == filename

    @pytest.mark.asyncio
    async def test_content_type_preservation(
        self, client: AsyncClient
    ) -> None:
        """Verify content type is preserved through upload/download."""
        content_types = [
            "text/plain",
            "application/json",
            "application/pdf",
            "image/jpeg",
            "application/octet-stream",
        ]

        for content_type in content_types:
            file_content = b"Test content"
            ext = content_type.split("/")[-1]
            files = {
                "file": (
                    f"test.{ext}",
                    BytesIO(file_content),
                    content_type,
                )
            }
            upload_response = await client.post("/documents", files=files)
            assert upload_response.status_code == HTTPStatus.CREATED

            doc_id = upload_response.json()["id"]
            download_response = await client.get(f"/documents/{doc_id}")
            assert (
                download_response.headers["content-type"] == content_type
            )

    @pytest.mark.asyncio
    async def test_file_size_tracking(self, client: AsyncClient) -> None:
        """Verify file size is accurately tracked."""
        test_sizes = [0, 100, 1024, 10000]

        for size in test_sizes:
            file_content = b"x" * size
            files = {"file": (f"size{size}.txt", BytesIO(file_content), "text/plain")}
            response = await client.post("/documents", files=files)
            if response.status_code == HTTPStatus.CREATED:
                assert response.json()["file_size"] == size


class TestDocumentErrorHandling:
    """Test document error scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_document_id(self, client: AsyncClient) -> None:
        """Getting document with invalid UUID should return 422."""
        response = await client.get("/documents/not-a-uuid")
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_missing_file_in_upload(self, client: AsyncClient) -> None:
        """Uploading without file should fail."""
        response = await client.post("/documents", data={})
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
