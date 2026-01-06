"""User table and related API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict, EmailStr, ValidationInfo, field_validator
from sqlmodel import Field, SQLModel

from {{ project_slug }}.models.base import TimestampedTable
from {{ project_slug }}.models.shared import OrganizationInfo

# Constants for validation
MAX_NAME_LENGTH = 100


class UserBase(SQLModel):
    email: EmailStr = Field(
        ..., description="User email address", examples=["user@example.com"]
    )
    name: str = Field(..., min_length=1, description="User full name")


class User(TimestampedTable, UserBase, table=True):
    __tablename__ = "app_user"
    pass


class UserCreate(UserBase):
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str, info: ValidationInfo) -> str:  # noqa: ARG003
        """Validate user name field.

        Args:
            value: The name value to validate
            info: Pydantic validation context

        Returns:
            The validated and trimmed name

        Raises:
            ValueError: If name is empty/whitespace or exceeds max length
        """
        value = value.strip()
        if not value:
            msg = "Name cannot be empty or whitespace"
            raise ValueError(msg)
        if len(value) > MAX_NAME_LENGTH:
            msg = f"Name must be {MAX_NAME_LENGTH} characters or less"
            raise ValueError(msg)
        return value


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    organizations: list[OrganizationInfo] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class UserUpdate(SQLModel):
    email: str | None = None
    name: str | None = None
