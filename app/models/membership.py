from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import sqlalchemy as sa
from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models.base import TimestampedTable


class MembershipBase(SQLModel):
    user_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    organization_id: int = Field(
        sa_column=sa.Column(
            sa.Integer,
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        )
    )


class Membership(TimestampedTable, MembershipBase, table=True):
    __table_args__ = (
        sa.Index("ix_membership_user_id", "user_id"),
        sa.Index("ix_membership_organization_id", "organization_id"),
    )


class MembershipCreate(MembershipBase):
    pass


class MembershipRead(MembershipBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
