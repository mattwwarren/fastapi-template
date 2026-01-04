"""Shared response schemas used across multiple resources."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import ConfigDict
from sqlmodel import SQLModel


class OrganizationInfo(SQLModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class UserInfo(SQLModel):
    id: UUID
    email: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
