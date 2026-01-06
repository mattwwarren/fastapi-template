"""Organization table and related API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from {{ project_slug }}.models.base import TimestampedTable
from {{ project_slug }}.models.shared import UserInfo


class OrganizationBase(SQLModel):
    name: str


class Organization(TimestampedTable, OrganizationBase, table=True):
    pass


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRead(OrganizationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    users: list[UserInfo] = Field(default_factory=list)

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class OrganizationUpdate(SQLModel):
    name: str | None = None
