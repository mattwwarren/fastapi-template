"""Unit tests for cache serialization helpers."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from fastapi_template.cache.exceptions import CacheSerializationError
from fastapi_template.cache.serialization import deserialize, serialize


class _Sample(BaseModel):
    id: int
    name: str


def test_serialize_round_trip() -> None:
    """A serialized model deserializes back to an equal typed model."""
    model = _Sample(id=1, name="alice")

    data = serialize(model)
    restored = deserialize(data, _Sample)

    assert isinstance(restored, _Sample)
    assert restored == model


def test_deserialize_without_model_returns_dict() -> None:
    """Without a model_class, JSON objects deserialize to a dict."""
    result = deserialize('{"id": 1, "name": "bob"}')

    assert result == {"id": 1, "name": "bob"}


def test_deserialize_without_model_returns_list() -> None:
    """Without a model_class, JSON arrays deserialize to a list."""
    result = deserialize("[1, 2, 3]")

    assert result == [1, 2, 3]


def test_deserialize_malformed_json_raises_cache_error() -> None:
    """Malformed JSON raises CacheSerializationError, not a raw JSON error."""
    with pytest.raises(CacheSerializationError):
        deserialize("{not-json", _Sample)


def test_deserialize_schema_mismatch_raises_cache_error() -> None:
    """Valid JSON that fails model validation raises CacheSerializationError."""
    with pytest.raises(CacheSerializationError):
        deserialize('{"id": "not-an-int", "name": 5}', _Sample)


def test_deserialize_malformed_json_without_model_raises_cache_error() -> None:
    """Malformed JSON also wraps into CacheSerializationError with no model_class."""
    with pytest.raises(CacheSerializationError):
        deserialize("{not-json")
