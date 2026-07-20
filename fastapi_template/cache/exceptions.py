"""Cache-specific exceptions."""

from __future__ import annotations


class CacheError(Exception):
    """Base exception for cache-related errors.

    Raised when cache operations fail in a way that requires explicit
    handling (e.g., serialization errors).

    Note: Most cache operations gracefully degrade on failure (returning
    None or False) rather than raising. This exception hierarchy is reserved
    for errors the caller may want to catch explicitly.
    """


class CacheSerializationError(CacheError):
    """Raised when serialization or deserialization fails.

    ``deserialize`` wraps malformed-JSON and schema-mismatch failures into
    this type so ``cache_get`` has a single exception to catch and treat as
    a cache miss.
    """
