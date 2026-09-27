from collections.abc import Callable, Mapping
from typing import Any

from fastapi import Request
from starlette.responses import Response

from slowapi.errors import RateLimitExceeded


class Limiter:
    enabled: bool
    _auto_check: bool
    _storage_uri: str | None
    _storage_options: dict[str, Any]
    _in_memory_fallback: list[Any]
    _in_memory_fallback_enabled: bool
    _storage: Any
    _limiter: Any
    _storage_dead: bool

    def __init__(
        self,
        key_func: Callable[..., str],
        default_limits: list[str | Callable[..., str]] = ...,
        application_limits: list[str | Callable[..., str]] = ...,
        headers_enabled: bool = ...,
        strategy: str | None = ...,
        storage_uri: str | None = ...,
        storage_options: Mapping[str, object] | None = ...,
        auto_check: bool = ...,
        swallow_errors: bool = ...,
        in_memory_fallback: list[str | Callable[..., str]] = ...,
        in_memory_fallback_enabled: bool = ...,
        retry_after: str | None = ...,
        key_prefix: str = ...,
        enabled: bool = ...,
        config_filename: str | None = ...,
        key_style: str = ...,
    ) -> None: ...

    def _check_request_limit(
        self, request: Request, handler: Callable[..., Any] | None, in_middleware: bool = ...
    ) -> None: ...

    def _inject_headers(self, response: Response, view_rate_limit: Any) -> Response: ...


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response: ...
