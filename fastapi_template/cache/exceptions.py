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


class CachePiiViolationError(CacheError):
    """Raised when a PII-marked model is passed to ``cache_set``.

    ``cache_set`` (and, transitively, the ``@cached`` decorator) refuses to
    serialize a model whose class declares ``pii: ClassVar[bool] = True`` --
    see ARCHITECTURE.md Invariant 10. Unlike the rest of this hierarchy this
    is not a degraded-infrastructure failure and must not be swallowed into
    a ``False`` return or an error metric.
    """
