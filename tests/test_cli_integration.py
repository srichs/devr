"""Integration-style CLI tests using temporary git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from devr.cli import app
from devr.templates import DEFAULT_TOOLCHAIN

runner = CliRunner()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_git_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "devr@example.com")
    _git(repo, "config", "user.name", "devr-tests")


def _fake_venv_python(repo: Path) -> Path:
    py = repo / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")
    return py


def test_check_changed_in_temp_git_repo_scopes_python_targets(
    monkeypatch, tmp_path: Path
) -> None:
    _init_git_repo(tmp_path)
    _fake_venv_python(tmp_path)

    tracked_py = tmp_path / "tracked.py"
    tracked_py.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("initial\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.py", "notes.md")
    _git(tmp_path, "commit", "-m", "initial")

    tracked_py.write_text("value = 2\n", encoding="utf-8")
    (tmp_path / "new_module.pyi").write_text("def run() -> None: ...\n", encoding="utf-8")
    (tmp_path / "todo.txt").write_text("todo\n", encoding="utf-8")

    calls: list[tuple[str, list[str]]] = []

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["check", "--changed", "--fast"])

    assert result.exit_code == 0
    assert calls == [
        ("ruff", ["check", "tracked.py", "new_module.pyi"]),
        ("ruff", ["format", "--check", "tracked.py", "new_module.pyi"]),
        ("mypy", ["tracked.py", "new_module.pyi"]),
    ]


def test_init_in_temp_git_repo_writes_precommit_and_installs_hook(
    monkeypatch, tmp_path: Path
) -> None:
    _init_git_repo(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")

    calls: list[tuple[str, list[str]]] = []

    def _create_venv(_root: Path, venv_dir: Path, python_exe=None) -> None:
        del python_exe
        py = venv_dir / "bin" / "python"
        py.parent.mkdir(parents=True, exist_ok=True)
        py.write_text("", encoding="utf-8")

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devr.cli.create_venv", _create_venv)
    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / ".pre-commit-config.yaml").exists()
    assert calls == [
        ("pip", ["install", "-U", "pip", "setuptools", "wheel"]),
        ("pip", ["install", *DEFAULT_TOOLCHAIN]),
        ("pip", ["install", "-e", "."]),
        ("pre_commit", ["install"]),
    ]
