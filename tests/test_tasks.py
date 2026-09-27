"""Tests for the copier post-generation tasks in _tasks.py."""

import importlib.util
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

TASKS_PATH = Path(__file__).resolve().parent.parent / "_tasks.py"
GIT = shutil.which("git")


def _load_tasks_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_tasks", TASKS_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(cwd: Path, *args: str) -> None:
    assert GIT is not None
    subprocess.run([GIT, *args], cwd=cwd, check=True, capture_output=True, text=True)


def _git_path() -> str:
    assert GIT is not None
    return GIT


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    return path


def _init_repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    main = _init_repo(tmp_path / "main")
    (main / "README.md").write_text("hello\n")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "initial")
    worktree = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(worktree))
    return main, worktree


def _which_without(*missing: str) -> Callable[[str], str | None]:
    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name in missing:
            return None
        return real_which(name)

    return fake_which


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep git from reading the developer's config or discovering repos above tmp_path."""
    assert GIT is not None, "git binary is required for these tests"
    gitconfig = tmp_path.parent / f"{tmp_path.name}.gitconfig"
    gitconfig.write_text(
        "[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))


@pytest.fixture
def tasks() -> ModuleType:
    return _load_tasks_module()


def test_install_precommit_skips_when_not_a_git_repo(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    result = tasks.install_precommit()

    captured = capsys.readouterr()
    assert result is False
    assert "Not a git repository" in captured.out
    assert "git init" in captured.out
    assert captured.err == ""


def test_install_precommit_skips_in_linked_worktree(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main, worktree = _init_repo_with_worktree(tmp_path)
    monkeypatch.chdir(worktree)

    result = tasks.install_precommit()

    captured = capsys.readouterr()
    assert result is False
    assert "worktree" in captured.out
    assert "shared across all worktrees" in captured.out
    assert captured.err == ""
    assert not (main / ".git" / "hooks" / "pre-commit").exists()


def test_install_precommit_installs_hooks_in_real_repo(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []\n")
    monkeypatch.chdir(tmp_path)

    result = tasks.install_precommit()

    captured = capsys.readouterr()
    assert result is True
    assert (tmp_path / ".git" / "hooks" / "pre-commit").exists()
    assert "Pre-commit hooks installed" in captured.out
    assert captured.err == ""


def test_install_precommit_skips_when_pre_commit_binary_missing(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tasks.shutil, "which", _which_without("pre-commit"))

    result = tasks.install_precommit()

    captured = capsys.readouterr()
    assert result is False
    assert "pre-commit not found" in captured.out
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()


def test_install_precommit_skips_when_git_binary_missing(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tasks.shutil, "which", _which_without("git"))

    result = tasks.install_precommit()

    captured = capsys.readouterr()
    assert result is False
    assert "Not a git repository" in captured.out
    assert captured.err == ""


def test_install_precommit_reports_real_failure(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path / "project")
    monkeypatch.chdir(tmp_path / "project")
    failing_precommit = tmp_path / "bin" / "pre-commit"
    failing_precommit.parent.mkdir()
    failing_precommit.write_text("#!/bin/sh\nexit 1\n")
    failing_precommit.chmod(0o755)
    real_which = shutil.which

    def which_failing_precommit(name: str) -> str | None:
        if name == "pre-commit":
            return str(failing_precommit)
        return real_which(name)

    monkeypatch.setattr(tasks.shutil, "which", which_failing_precommit)

    result = tasks.install_precommit()

    captured = capsys.readouterr()
    assert result is False
    assert "Failed to install pre-commit hooks" in captured.err
    assert "pre-commit install" in captured.out


def test_git_dirs_returns_none_outside_git_repo(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert tasks._git_dirs(_git_path()) is None


def test_git_dirs_equal_in_normal_repo(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    dirs = tasks._git_dirs(_git_path())

    assert dirs is not None
    git_dir, common_dir = dirs
    assert Path(git_dir).resolve() == Path(common_dir).resolve()


def test_git_dirs_equal_in_subdirectory_of_normal_repo(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repo(tmp_path)
    subdir = tmp_path / "services" / "generated"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    dirs = tasks._git_dirs(_git_path())

    assert dirs is not None
    git_dir, common_dir = dirs
    assert Path(git_dir).resolve() == Path(common_dir).resolve()


def test_git_dirs_differs_for_linked_worktree(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, worktree = _init_repo_with_worktree(tmp_path)
    monkeypatch.chdir(worktree)

    dirs = tasks._git_dirs(_git_path())

    assert dirs is not None
    git_dir, common_dir = dirs
    assert Path(git_dir).resolve() != Path(common_dir).resolve()


def test_main_summary_warns_when_hooks_not_installed(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tasks.shutil, "which", _which_without("uv"))

    exit_code = tasks.main()

    summary = capsys.readouterr().out.split("Step 4/4")[-1]
    assert exit_code == 0
    assert "Pre-commit hooks are not installed" in summary


def test_main_summary_confirms_when_hooks_installed(
    tasks: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(tasks.shutil, "which", _which_without("uv"))

    exit_code = tasks.main()

    summary = capsys.readouterr().out.split("Step 4/4")[-1]
    assert exit_code == 0
    assert "ready for development" in summary
    assert "not installed" not in summary
