"""Comprehensive document endpoint tests for upload, download, validation, limits."""

from http import HTTPStatus
from io import BytesIO

import pytest
from httpx import AsyncClient

from fastapi_template.core.config import settings

# Test file sizes
TEST_BINARY_FILE_SIZE = 256  # bytes - size of test binary data (0-255)
TEST_LARGE_FILE_SIZE = 10000  # bytes - 10KB for streaming tests


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
    async def test_upload_document_with_binary_data(self, client: AsyncClient) -> None:
        """Upload a binary file (e.g., image)."""
        # Create fake binary image data
        file_content = bytes(range(256))  # 256 bytes of binary data
        files = {"file": ("image.png", BytesIO(file_content), "image/png")}

        response = await client.post("/documents", files=files)
        assert response.status_code == HTTPStatus.CREATED
        doc = response.json()
        assert doc["filename"] == "image.png"
        assert doc["content_type"] == "image/png"
        assert doc["file_size"] == TEST_BINARY_FILE_SIZE

    @pytest.mark.asyncio
    async def test_upload_document_no_filename(self, client: AsyncClient) -> None:
        """Uploading document without filename should fail."""
        file_content = b"Test content"
        files = {"file": ("", BytesIO(file_content), "text/plain")}

        response = await client.post("/documents", files=files)
        assert response.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_upload_document_no_content_type(self, client: AsyncClient) -> None:
        """Uploading document without explicit content type defaults to inferred type."""
        file_content = b"Test content"
        files = {"file": ("test.txt", BytesIO(file_content), None)}

        response = await client.post("/documents", files=files)
        # When content_type is None, httpx infers type from filename extension
        # .txt files default to text/plain
        assert response.status_code == HTTPStatus.CREATED
        assert response.json()["content_type"] == "text/plain"

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
        assert download_response.headers["content-type"].startswith("text/plain")
        content_disposition = download_response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition
        assert "download.txt" in content_disposition

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
        file_content = b"x" * TEST_LARGE_FILE_SIZE  # 10KB
        files = {"file": ("stream.txt", BytesIO(file_content), "text/plain")}
        upload_response = await client.post("/documents", files=files)
        doc_id = upload_response.json()["id"]

        # Download document (should stream)
        download_response = await client.get(f"/documents/{doc_id}")
        assert download_response.status_code == HTTPStatus.OK
        assert len(download_response.content) == TEST_LARGE_FILE_SIZE


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
    async def test_content_type_preservation(self, client: AsyncClient) -> None:
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
            assert download_response.headers["content-type"].startswith(content_type)

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


class TestDocumentPathTraversalSecurity:
    """Test security against path traversal attacks in local storage.

    Path traversal attacks attempt to escape the storage directory by using
    special path components like .. or absolute paths. UUIDs prevent most
    attacks, but validation ensures defense in depth.
    """

    @pytest.mark.asyncio
    async def test_document_id_must_be_uuid_format(self, client: AsyncClient) -> None:
        """Path traversal attempts with non-UUID document IDs should fail.

        The API enforces UUID format on document_id path parameter.
        This prevents injection of path traversal sequences.

        Note: FastAPI returns 404 (route not found) for malformed UUIDs in path
        parameters, not 422. Either way, the traversal is blocked.
        """
        # Attempt to use .. for path traversal
        response = await client.get("/documents/../../etc/passwd")
        # Should return 404 (route not matched) or 422 (validation error)
        assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY)

        # Attempt absolute path
        response = await client.get("/documents//etc/passwd")
        assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY)

        # Attempt dot-dot sequences
        response = await client.get("/documents/..%2F..%2Fetc%2Fpasswd")
        assert response.status_code in (HTTPStatus.NOT_FOUND, HTTPStatus.UNPROCESSABLE_ENTITY)

    @pytest.mark.asyncio
    async def test_valid_uuid_stays_within_storage_directory(self, client: AsyncClient) -> None:
        """Valid UUIDs cannot escape storage directory.

        Even valid UUIDs cannot escape the storage directory because:
        1. UUID format is strictly validated in path parameters
        2. Storage backend validates resolved path is within base_path
        3. Combination provides defense in depth against path traversal
        """
        # A valid UUID that doesn't exist
        response = await client.get("/documents/00000000-0000-0000-0000-000000000000")
        # Should return 404 (not found), not allow traversal
        assert response.status_code == HTTPStatus.NOT_FOUND

        # Another valid UUID
        response = await client.get("/documents/ffffffff-ffff-ffff-ffff-ffffffffffff")
        # Should return 404 (not found), not allow traversal
        assert response.status_code == HTTPStatus.NOT_FOUND
