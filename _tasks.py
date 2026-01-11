#!/usr/bin/env python3
"""Post-generation tasks for FastAPI template.

This script runs automatically after copier generates a new project.
It handles initial setup tasks that would otherwise be manual.
"""

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


ERROR_DOTENV_NOT_FOUND = "dotenv.example not found - this shouldn't happen"
ERROR_COPY_DOTENV_FAILED = "Failed to copy dotenv.example to .env"


def copy_env_file() -> None:
    """Copy dotenv.example to .env if .env doesn't exist."""
    log_step("Step 1/3: Environment Configuration")

    env_example = Path("dotenv.example")
    env_file = Path(".env")

    if not env_example.exists():
        log_error(ERROR_DOTENV_NOT_FOUND)
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
        log_error(f"{ERROR_COPY_DOTENV_FAILED}: {exc}")


def run_uv_sync() -> None:
    """Install dependencies using uv sync --dev."""
    log_step("Step 2/3: Install Dependencies")

    # Check if uv is available
    uv_path = shutil.which("uv")
    if not uv_path:
        log_warning("uv not found - skipping dependency installation")
        log_warning("Install uv: https://docs.astral.sh/uv/")
        log_warning("Then run: uv sync --dev")
        return

    try:
        subprocess.run(  # noqa: S603 - uv_path from shutil.which(), trusted
            [uv_path, "sync", "--dev"],
            check=True,
            capture_output=True,
            text=True,
        )
        log_success("Dependencies installed successfully")
    except subprocess.CalledProcessError as exc:
        log_error(f"Failed to install dependencies: {exc}")
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        log_warning("You can manually install later with: uv sync --dev")
    except Exception as exc:
        log_error(f"Unexpected error during uv sync: {exc}")


def run_alembic_upgrade() -> None:
    """Run alembic upgrade head to create database schema."""
    log_step("Step 3/3: Database Migration")

    # Check if uv is available for running alembic
    uv_path = shutil.which("uv")
    if not uv_path:
        log_warning("uv not found - skipping database migration")
        log_warning("After installing uv, run: uv run alembic upgrade head")
        return

    # Check if alembic is available
    try:
        subprocess.run(  # noqa: S603 - uv_path from shutil.which(), trusted
            [uv_path, "run", "alembic", "--version"],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        log_warning("Alembic not yet installed - skipping database migration")
        log_warning("After uv sync completes, run: uv run alembic upgrade head")
        return

    # Check if DATABASE_URL is set (basic check)
    env_file = Path(".env")
    if env_file.exists():
        env_content = env_file.read_text()
        if "DATABASE_URL=postgresql" not in env_content:
            log_warning("DATABASE_URL not configured in .env")
            log_warning("Configure database connection, then run: uv run alembic upgrade head")
            return

    try:
        subprocess.run(  # noqa: S603 - uv_path from shutil.which(), trusted
            [uv_path, "run", "alembic", "upgrade", "head"],
            check=True,
            capture_output=True,
            text=True,
        )
        log_success("Database schema created successfully")
    except subprocess.CalledProcessError as exc:
        # Database migration failure is common (DB not running, credentials wrong)
        # This is not critical - user can run it manually
        log_warning("Database migration failed - this is common if:")
        log_warning("  • PostgreSQL is not running")
        log_warning("  • DATABASE_URL in .env is incorrect")
        log_warning("  • Database doesn't exist yet")
        log_warning("")
        log_warning(f"Error details: {exc}")
        log_warning("Fix the issue, then run: uv run alembic upgrade head")
    except Exception as exc:
        log_error(f"Unexpected error during alembic upgrade: {exc}")


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
