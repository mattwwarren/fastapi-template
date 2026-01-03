from datetime import datetime

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class TimestampedTable(SQLModel):
    id: int | None = Field(
        default=None,
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"autoincrement": True},
    )
    created_at: datetime = Field(
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "nullable": False,
        }
    )
    updated_at: datetime = Field(
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "server_onupdate": sa.func.now(),
            "nullable": False,
        }
    )
