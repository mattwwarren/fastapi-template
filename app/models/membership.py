"""Membership table and API schemas for user-organization links."""

from __future__ import annotations

from datetime import datetime
from typing import ClassVar
from uuid import UUID

import sqlalchemy as sa
from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models.base import TimestampedTable


class MembershipBase(SQLModel):
    user_id: UUID = Field(
        sa_column=sa.Column(
            sa.UUID(as_uuid=True),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    organization_id: UUID = Field(
        sa_column=sa.Column(
            sa.UUID(as_uuid=True),
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
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
