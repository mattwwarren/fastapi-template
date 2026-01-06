"""User table and related API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from {{ project_slug }}.models.base import TimestampedTable
from {{ project_slug }}.models.shared import OrganizationInfo


class UserBase(SQLModel):
    email: str
    name: str


class User(TimestampedTable, UserBase, table=True):
    __tablename__ = "app_user"
    pass


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    organizations: list[OrganizationInfo] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class UserUpdate(SQLModel):
    email: str | None = None
    name: str | None = None
