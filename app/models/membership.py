from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models.base import TimestampedTable


class MembershipBase(SQLModel):
    user_id: int = Field(foreign_key="app_user.id")
    organization_id: int = Field(foreign_key="organization.id")


class Membership(TimestampedTable, MembershipBase, table=True):
    pass


class MembershipCreate(MembershipBase):
    pass


class MembershipRead(MembershipBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
