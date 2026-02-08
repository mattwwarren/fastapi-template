"""Cache-specific exceptions."""

from __future__ import annotations


class CacheError(Exception):
    """Base exception for cache-related errors.

    Raised when cache operations fail in a way that requires
    explicit handling (e.g., serialization errors, connection failures).

    Note: Most cache operations gracefully degrade on failure
    (returning None or False) rather than raising exceptions.
    This exception is reserved for unrecoverable errors.
    """


class CacheSerializationError(CacheError):
    """Raised when serialization/deserialization fails.

    Example:
        Attempting to cache a non-serializable object.
    """


class CacheConnectionError(CacheError):
    """Raised when Redis connection is unavailable.

    Example:
        Redis server is down and operation cannot proceed.
    """
