from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class TimestampedTable(SQLModel):
    id: UUID | None = Field(  # type: ignore[call-overload]
        default=None,
        primary_key=True,
        sa_type=PGUUID(as_uuid=True),
        sa_column_kwargs={
            "server_default": sa.text("gen_random_uuid()"),
            "nullable": False,
        },
    )
    created_at: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "nullable": False,
        },
    )
    updated_at: datetime = Field(
        sa_type=sa.DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "nullable": False,
        },
    )
