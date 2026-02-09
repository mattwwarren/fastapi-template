"""JSON serialization with Pydantic model support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    pass

T = TypeVar("T", bound=BaseModel)


def serialize(value: BaseModel) -> str:
    """Serialize Pydantic model to JSON string.

    Args:
        value: Pydantic model to serialize

    Returns:
        JSON string

    Examples:
        # Pydantic model
        serialize(User(id=123, name="Alice"))
        # '{"id": 123, "name": "Alice"}'
    """
    return value.model_dump_json()


def deserialize[T: BaseModel](data: str, model_class: type[T] | None = None) -> T | dict | list:
    """Deserialize JSON string to Python object.

    Args:
        data: JSON string from Redis
        model_class: Optional Pydantic model class for validation

    Returns:
        Pydantic model instance or dict/list

    Examples:
        # Without model class (returns dict)
        deserialize('{"id": 123}')
        # {'id': 123}

        # With Pydantic model class (returns User instance)
        deserialize('{"id": 123, "name": "Alice"}', User)
        # User(id=123, name="Alice")
    """
    if model_class and issubclass(model_class, BaseModel):
        return model_class.model_validate_json(data)
    return json.loads(data)
