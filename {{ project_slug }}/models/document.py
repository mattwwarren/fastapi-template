"""Document table for binary file storage example."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

import sqlalchemy as sa
from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from {{ project_slug }}.models.base import TimestampedTable


class DocumentBase(SQLModel):
    """Shared document metadata fields."""

    filename: str
    content_type: str
    file_size: int


class Document(TimestampedTable, DocumentBase, table=True):
    """Document table with binary file storage.

    Example of storing binary data in PostgreSQL using LargeBinary.
    For production use, consider object storage (S3, Azure Blob, etc.)
    for files larger than a few MB.
    """

    __tablename__ = "document"

    file_data: bytes = Field(sa_column=sa.Column(sa.LargeBinary, nullable=False))


class DocumentCreate(SQLModel):
    """Schema for creating a document.

    Note: file_data is passed separately via UploadFile in the API.
    These fields come from form metadata.
    """

    filename: str
    content_type: str
    file_size: int
    file_data: bytes


class DocumentRead(DocumentBase):
    """Schema for reading document metadata.

    Excludes file_data to avoid loading large blobs in list views.
    Use the download endpoint to stream file content.
    """

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
