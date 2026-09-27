"""Regression test pinning the verified middleware execution order.

Guards against main.py's module docstring drifting from
app.user_middleware again.
"""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from fastapi_template.core.logging import LoggingMiddleware
from fastapi_template.main import app


def test_active_middleware_executes_logging_then_slowapi_then_cors() -> None:
    """Starlette executes middleware in reverse of add order."""
    assert [m.cls for m in app.user_middleware] == [
        LoggingMiddleware,
        SlowAPIMiddleware,
        CORSMiddleware,
    ]
