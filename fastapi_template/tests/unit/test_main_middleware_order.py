"""Regression test pinning the verified middleware execution order.

Guards against main.py's module docstring drifting from
app.user_middleware again.
"""

from __future__ import annotations

import importlib

from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from fastapi_template import main as main_module
from fastapi_template.core.logging import LoggingMiddleware


def test_active_middleware_executes_logging_then_slowapi_then_cors() -> None:
    """Starlette executes middleware in reverse of add order.

    Reloads main.py for a fresh FastAPI instance rather than importing the
    shared `app` singleton: other fixtures (e.g. conftest's
    client_bypass_auth) mutate app.user_middleware in place with no
    teardown, so under -n auto whichever test ran first leaks its
    middleware stack into this assertion.
    """
    fresh_main = importlib.reload(main_module)
    assert [m.cls for m in fresh_main.app.user_middleware] == [
        LoggingMiddleware,
        SlowAPIMiddleware,
        CORSMiddleware,
    ]
