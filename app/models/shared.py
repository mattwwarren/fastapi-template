from datetime import datetime
from typing import ClassVar

from pydantic import ConfigDict
from sqlmodel import SQLModel


class OrganizationInfo(SQLModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)


class UserInfo(SQLModel):
    id: int
    email: str
    name: str
    created_at: datetime
    updated_at: datetime

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
