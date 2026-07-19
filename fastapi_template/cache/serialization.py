"""JSON serialization with Pydantic model support.

Deserialization failures (malformed JSON or schema mismatch) are wrapped into
``CacheSerializationError`` so callers -- notably ``cache_get`` -- have a single
exception type to catch and treat as a cache miss, rather than reasoning about
raw ``json.JSONDecodeError`` / ``pydantic.ValidationError``.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from fastapi_template.cache.exceptions import CacheSerializationError


def serialize(value: BaseModel) -> str:
    """Serialize a Pydantic model to a JSON string.

    Args:
        value: Pydantic model to serialize.

    Returns:
        JSON string.
    """
    return value.model_dump_json()


def deserialize[T: BaseModel](data: str | bytes, model_class: type[T] | None = None) -> T | dict | list:
    """Deserialize a JSON string into a Python object.

    Args:
        data: JSON payload retrieved from Redis (``str`` when the client uses
            ``decode_responses=True``; ``bytes`` otherwise).
        model_class: Optional Pydantic model class for typed validation.

    Returns:
        A ``model_class`` instance when supplied, otherwise a dict/list.

    Raises:
        CacheSerializationError: If the data is not valid JSON or fails
            validation against ``model_class``.
    """
    try:
        if model_class is not None and issubclass(model_class, BaseModel):
            return model_class.model_validate_json(data)
        return json.loads(data)
    except Exception as exc:
        msg = f"Failed to deserialize cached value: {exc}"
        raise CacheSerializationError(msg) from exc
