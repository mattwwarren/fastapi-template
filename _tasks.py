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
    print(f"\n{'=' * 60}")
    print(f"  {message}")
    print(f"{'=' * 60}\n")


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
    log_step("Step 1/4: Environment Configuration")

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
    log_step("Step 2/4: Install Dependencies")

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


def _run_git(git_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git plumbing command; never raise, treat any failure as exit 1."""
    try:
        return subprocess.run(  # noqa: S603 - git_path from shutil.which(), trusted
            [git_path, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return subprocess.CompletedProcess(args=[git_path, *args], returncode=1, stdout="", stderr="")


def _git_dirs(git_path: str) -> tuple[str, str] | None:
    """Return (git-dir, git-common-dir) for the cwd, or None if not a git work tree."""
    git_dir = _run_git(git_path, "rev-parse", "--git-dir")
    if git_dir.returncode != 0:
        return None
    common_dir = _run_git(git_path, "rev-parse", "--git-common-dir")
    if common_dir.returncode != 0:
        return None
    return git_dir.stdout.strip(), common_dir.stdout.strip()


def install_precommit() -> bool:
    """Install pre-commit hooks, if this looks like a git repo we should touch.

    Returns:
        True if hooks were installed, False if the step was skipped or failed.
    """
    log_step("Step 3/4: Install Pre-commit Hooks")

    git_path = shutil.which("git")
    dirs = _git_dirs(git_path) if git_path else None
    if dirs is None:
        log_warning("Not a git repository - skipping pre-commit hook installation")
        log_warning("Run 'git init && pre-commit install' when you initialize your repo")
        return False

    git_dir, common_dir = dirs
    # A linked worktree shares hooks with every other worktree via the common dir.
    if Path(git_dir).resolve() != Path(common_dir).resolve():
        log_warning("Generated project is inside a git worktree - skipping pre-commit hook installation")
        log_warning("Pre-commit hooks are shared across all worktrees of this repository")
        log_warning("Run 'pre-commit install' from the main worktree when you're ready")
        return False

    precommit_path = shutil.which("pre-commit")
    if not precommit_path:
        log_warning("pre-commit not found - skipping hook installation")
        log_warning("Install with: uv tool install pre-commit")
        log_warning("Then run: pre-commit install")
        return False

    try:
        subprocess.run(  # noqa: S603 - precommit_path from shutil.which(), trusted
            [precommit_path, "install"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        log_error(f"Failed to install pre-commit hooks: {exc}")
        log_warning("You can manually install later with: pre-commit install")
        return False
    log_success("Pre-commit hooks installed")
    return True


def main() -> int:
    """Run all post-generation tasks.

    Returns:
        Always returns 0 - failures are informational, not critical
    """
    print("\n" + "=" * 60)
    print("  FastAPI Template - Post-Generation Setup")
    print("=" * 60)

    # Step 1: Copy .env file
    copy_env_file()

    # Step 2: Install dependencies
    run_uv_sync()

    # Step 3: Install pre-commit hooks
    hooks_installed = install_precommit()

    # Final summary (Step 4/4)
    log_step("Step 4/4: Setup Complete")
    print("Your project is ready for development!")
    if not hooks_installed:
        log_warning("Pre-commit hooks are not installed yet - see Step 3 above to finish setup")

    # Always return 0 - failures are expected (no database, etc.)
    # and should not prevent copier from completing successfully
    return 0


if __name__ == "__main__":
    sys.exit(main())
