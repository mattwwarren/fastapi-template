"""Regression tests pinning the installed fastapi/starlette floor versions.

Issue #21 upgrades fastapi 0.128→0.139.x and starlette 0.50→1.x. No existing
test asserts the installed dependency versions, so an accidental downgrade (or a
stale lockfile) would go unnoticed. These tests read the *installed* package
metadata via ``importlib.metadata`` and assert the resolved versions meet the
floors declared in ``pyproject.toml``.

They intentionally fail against the pre-upgrade pins (fastapi 0.138.2 /
starlette 0.52.1), giving a concrete red→green signal for the upgrade.
"""

from __future__ import annotations

from importlib.metadata import version

from packaging.version import Version


def test_fastapi_at_least_0_139() -> None:
    """Installed fastapi must be >= 0.139.0 (issue #21 floor)."""
    assert Version(version("fastapi")) >= Version("0.139.0")


def test_starlette_at_least_1_0() -> None:
    """Installed starlette must be >= 1.0.0 (issue #21 floor)."""
    assert Version(version("starlette")) >= Version("1.0.0")


def test_ruff_below_0_16() -> None:
    """Installed ruff must stay on the 0.15.x line (issue #49 floor+ceiling).

    ruff 0.16 stabilizes PLR0917 (too-many-positional-arguments) out of
    preview, which this template's pytest fixtures/factories intentionally
    exceed. This is a stopgap ceiling, not a permanent one: issue #50
    (safe dependency sweep) is responsible for lifting it to ruff 0.16.x
    once the two PLR0917 sites in tests/conftest.py and the 0.16
    formatter are handled there.
    """
    assert Version("0.15.22") <= Version(version("ruff")) < Version("0.16.0")
