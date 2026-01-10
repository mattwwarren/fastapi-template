#!/usr/bin/env python3
"""Post-generation tasks for FastAPI template.

This script runs automatically after copier generates a new project.
It handles initial setup tasks that would otherwise be manual.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def log_step(message: str) -> None:
    """Print a step message with formatting."""
    print(f"\n{'='*60}")
    print(f"  {message}")
    print(f"{'='*60}\n")


def log_success(message: str) -> None:
    """Print a success message."""
    print(f"✓ {message}")


def log_error(message: str) -> None:
    """Print an error message."""
    print(f"✗ {message}", file=sys.stderr)


def log_warning(message: str) -> None:
    """Print a warning message."""
    print(f"⚠ {message}")


def copy_env_file() -> None:
    """Copy dotenv.example to .env if .env doesn't exist."""
    log_step("Step 1/3: Environment Configuration")

    env_example = Path("dotenv.example")
    env_file = Path(".env")

    if not env_example.exists():
        log_error("dotenv.example not found - this shouldn't happen")
        return

    if env_file.exists():
        log_warning(".env already exists - skipping copy")
        log_warning("If you want fresh defaults, run: cp dotenv.example .env")
        return

    try:
        shutil.copy2(env_example, env_file)
        log_success("Created .env from dotenv.example")
        log_warning("IMPORTANT: Edit .env and set DATABASE_URL before running the app")
    except Exception as exc:
        log_error(f"Failed to copy dotenv.example to .env: {exc}")


def run_uv_sync() -> bool:
    """Install dependencies using uv sync --dev.

    Returns:
        True if successful or uv not available, False on error
    """
    log_step("Step 2/3: Install Dependencies")

    # Check if uv is available
    if not shutil.which("uv"):
        log_warning("uv not found - skipping dependency installation")
        log_warning("Install uv: https://docs.astral.sh/uv/")
        log_warning("Then run: uv sync --dev")
        return True

    try:
        result = subprocess.run(
            ["uv", "sync", "--dev"],
            check=True,
            capture_output=True,
            text=True,
        )
        log_success("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as exc:
        log_error(f"Failed to install dependencies: {exc}")
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        log_warning("You can manually install later with: uv sync --dev")
        return False
    except Exception as exc:
        log_error(f"Unexpected error during uv sync: {exc}")
        return False


def run_alembic_upgrade() -> bool:
    """Run alembic upgrade head to create database schema.

    Returns:
        True if successful or alembic not available, False on error
    """
    log_step("Step 3/3: Database Migration")

    # Check if uv is available for running alembic
    if not shutil.which("uv"):
        log_warning("uv not found - skipping database migration")
        log_warning("After installing uv, run: uv run alembic upgrade head")
        return True

    # Check if alembic is available
    try:
        subprocess.run(
            ["uv", "run", "alembic", "--version"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        log_warning("Alembic not yet installed - skipping database migration")
        log_warning("After uv sync completes, run: uv run alembic upgrade head")
        return True

    # Check if DATABASE_URL is set (basic check)
    env_file = Path(".env")
    if env_file.exists():
        env_content = env_file.read_text()
        if "DATABASE_URL=postgresql" not in env_content:
            log_warning("DATABASE_URL not configured in .env")
            log_warning("Configure database connection, then run: uv run alembic upgrade head")
            return True

    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True,
        )
        log_success("Database schema created successfully")
        return True
    except subprocess.CalledProcessError as exc:
        # Database migration failure is common (DB not running, credentials wrong)
        # This is not critical - user can run it manually
        log_warning("Database migration failed - this is common if:")
        log_warning("  • PostgreSQL is not running")
        log_warning("  • DATABASE_URL in .env is incorrect")
        log_warning("  • Database doesn't exist yet")
        log_warning("")
        log_warning("Fix the issue, then run: uv run alembic upgrade head")
        return True  # Return True - this is expected, not a critical error
    except Exception as exc:
        log_error(f"Unexpected error during alembic upgrade: {exc}")
        return True  # Return True - user can fix manually


def main() -> int:
    """Run all post-generation tasks.

    Returns:
        Always returns 0 - failures are informational, not critical
    """
    print("\n" + "="*60)
    print("  FastAPI Template - Post-Generation Setup")
    print("="*60)

    # Step 1: Copy .env file
    copy_env_file()

    # Step 2: Install dependencies
    run_uv_sync()

    # Step 3: Run migrations
    run_alembic_upgrade()

    # Final summary
    print("\n" + "="*60)
    print("  Post-generation setup complete!")
    print("="*60)

    # Always return 0 - failures are expected (no database, etc.)
    # and should not prevent copier from completing successfully
    return 0


if __name__ == "__main__":
    sys.exit(main())
