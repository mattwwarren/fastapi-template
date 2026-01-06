"""Document upload and download endpoints with binary streaming."""

from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlmodel import col

from {{ project_slug }}.core.activity_logging import ActivityAction, log_activity_decorator
from {{ project_slug }}.core.config import settings
from {{ project_slug }}.db.session import SessionDep
from {{ project_slug }}.models.document import Document, DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])


def iter_file_chunks(data: bytes, chunk_size: int = 8192) -> Iterator[bytes]:
    """Yield chunks of binary data for streaming.

    Args:
        data: Binary data to stream
        chunk_size: Size of each chunk in bytes (default 8KB)

    Yields:
        Chunks of binary data
    """
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
@log_activity_decorator(ActivityAction.CREATE, "document")
async def upload_document(
    session: SessionDep,
    file: UploadFile = File(...),
) -> DocumentRead:
    """Upload a binary file and store in database.

    Args:
        session: Database session
        file: Uploaded file from multipart/form-data

    Returns:
        Document metadata (excluding file_data)

    Raises:
        HTTPException: If file has no filename or content type
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a filename",
        )

    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a content type",
        )

    # Read with size limit (+1 to detect oversized files)
    file_data = await file.read(settings.max_file_size_bytes + 1)
    file_size = len(file_data)

    if file_size > settings.max_file_size_bytes:
        max_mb = settings.max_file_size_bytes / 1024 / 1024
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {max_mb:.1f}MB",
        )

    document = Document(
        filename=file.filename,
        content_type=file.content_type,
        file_size=file_size,
        file_data=file_data,
    )

    session.add(document)
    await session.commit()
    await session.refresh(document)

    return DocumentRead.model_validate(document)


@router.get("/{document_id}")
@log_activity_decorator(ActivityAction.READ, "document")
async def download_document(
    document_id: UUID,
    session: SessionDep,
) -> StreamingResponse:
    """Download a document's binary content with streaming.

    Args:
        document_id: UUID of the document to download
        session: Database session

    Returns:
        StreamingResponse with file content

    Raises:
        HTTPException: If document not found
    """
    result = await session.execute(
        select(Document).where(col(Document.id) == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return StreamingResponse(
        iter_file_chunks(document.file_data),
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"',
        },
    )
