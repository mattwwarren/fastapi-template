from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class TimestampedTable(SQLModel):
    id: UUID = Field(
        sa_column_args=(PGUUID(as_uuid=True),),
        sa_column_kwargs={
            "primary_key": True,
            "server_default": sa.text("gen_random_uuid()"),
            "nullable": False,
        },
    )
    created_at: datetime = Field(
        sa_column_args=(sa.DateTime(timezone=True),),
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "nullable": False,
        },
    )
    updated_at: datetime = Field(
        sa_column_args=(sa.DateTime(timezone=True),),
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "server_onupdate": sa.func.now(),
            "nullable": False,
        },
    )
