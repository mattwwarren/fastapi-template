"""JSON serialization with Pydantic model support."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")


def serialize(value: Any) -> str:
    """Serialize value to JSON string.

    Supports:
    - Pydantic models (via .model_dump_json())
    - Native JSON types (dict, list, str, int, etc.)
    - UUID (converted to string)
    - Other types (converted to string via default=str)

    Args:
        value: Value to serialize

    Returns:
        JSON string

    Examples:
        # Pydantic model
        serialize(User(id=123, name="Alice"))
        # '{"id": 123, "name": "Alice"}'

        # Dict
        serialize({"key": "value"})
        # '{"key": "value"}'

        # UUID
        serialize(uuid.uuid4())
        # '"550e8400-e29b-41d4-a716-446655440000"'
    """
    # Import here to avoid circular dependency and support TYPE_CHECKING
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, default=str)


def deserialize(data: str, model_class: type[T] | None = None) -> T | Any:
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
    # Import here to avoid circular dependency and support TYPE_CHECKING
    from pydantic import BaseModel

    if model_class and issubclass(model_class, BaseModel):
        return model_class.model_validate_json(data)
    return json.loads(data)
