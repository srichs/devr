"""CLI behavior tests for devr commands."""

import subprocess
from pathlib import Path
from types import SimpleNamespace

from importlib.metadata import PackageNotFoundError

from typer.testing import CliRunner
from click.exceptions import Exit

from devr.cli import (
    app,
    ensure_toolchain,
    install_precommit_hook,
    install_project,
    write_precommit,
)
from devr.config import DevrConfig
from devr.templates import PRECOMMIT_LOCAL_HOOK_YAML

runner = CliRunner()


def test_version_flag_prints_version(monkeypatch) -> None:
    monkeypatch.setattr("devr.cli.version", lambda _: "1.2.3")

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "devr 1.2.3" in result.output


def test_check_prints_selected_venv(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.run_module", lambda *_, **__: 0)

    result = runner.invoke(app, ["check", "--fast"])

    assert result.exit_code == 0
    assert f"Using venv: {venv_path}" in result.output


def test_check_warns_when_staged_used_without_changed(
    monkeypatch, tmp_path: Path
) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.run_module", lambda *_, **__: 0)

    result = runner.invoke(app, ["check", "--staged", "--fast"])

    assert result.exit_code == 0
    assert "Warning: --staged has no effect without --changed." in result.output


def test_security_runs_pip_audit_and_bandit(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(venv_path=".venv"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["security"])

    assert result.exit_code == 0
    assert calls == [
        ("pip_audit", []),
        (
            "bandit",
            [
                "-r",
                ".",
                "-x",
                ".venv,venv,env,.git,__pycache__,.mypy_cache,.pytest_cache,.ruff_cache,.tox,.nox,build,dist",
            ],
        ),
    ]
    assert "✅ devr security passed" in result.output




def test_security_runs_bandit_even_when_pip_audit_fails(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[str] = []

    def _run_module(_venv, module: str, _args: list[str], **_kwargs) -> int:
        calls.append(module)
        return 1 if module == "pip_audit" else 0

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(venv_path=".venv"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["security"])

    assert result.exit_code == 1
    assert calls == ["pip_audit", "bandit"]
    assert "Security checks failed: pip-audit" in result.output


def test_security_reports_multiple_failures(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(venv_path=".venv"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.run_module", lambda *_args, **_kwargs: 1)

    result = runner.invoke(app, ["security"])

    assert result.exit_code == 1
    assert "Security checks failed: pip-audit, bandit" in result.output
def test_bandit_excludes_include_detected_relative_venv(tmp_path: Path) -> None:
    from devr.cli import _bandit_excludes

    excludes = _bandit_excludes(tmp_path, ".venv", tmp_path / "custom-venv")

    assert (
        excludes
        == ".venv,venv,env,.git,__pycache__,.mypy_cache,.pytest_cache,.ruff_cache,.tox,.nox,build,dist,custom-venv"
    )


def test_security_exits_when_no_venv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig())
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: None)

    result = runner.invoke(app, ["security"])

    assert result.exit_code == 2
    assert "No venv found. Run: devr init" in result.output


def test_devr_version_falls_back_when_package_not_installed(monkeypatch) -> None:
    def _raise(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("devr.cli.version", _raise)

    from devr.cli import _devr_version

    assert _devr_version() == "0.0.0"


def test_install_project_falls_back_to_non_editable(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    calls: list[list[str]] = []

    def _run_module(_venv, _module: str, args: list[str], **_kwargs) -> int:
        calls.append(args)
        return 1 if args == ["install", "-e", "."] else 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    install_project(tmp_path / ".venv", tmp_path)

    assert calls == [["install", "-e", "."], ["install", "."]]


def test_install_project_uses_requirements_file(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, _module, args, **_kwargs: calls.append(args) or 0,
    )

    install_project(tmp_path / ".venv", tmp_path)

    assert calls == [["install", "-r", "requirements.txt"]]


def test_install_project_warns_when_requirements_install_fails(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.run_module", lambda *_args, **_kwargs: 1)

    install_project(tmp_path / ".venv", tmp_path)

    out = capsys.readouterr().out
    assert "Warning: requirements install failed" in out


def test_install_project_warns_when_both_install_attempts_fail(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.run_module", lambda *_args, **_kwargs: 1)

    install_project(tmp_path / ".venv", tmp_path)

    out = capsys.readouterr().out
    assert "Warning: project install failed" in out


def test_install_project_skips_when_no_dependency_file(tmp_path: Path, capsys) -> None:
    install_project(tmp_path / ".venv", tmp_path)

    out = capsys.readouterr().out
    assert "No pyproject.toml or requirements.txt found" in out


def test_write_precommit_creates_default_file(tmp_path: Path) -> None:
    cfg = tmp_path / ".pre-commit-config.yaml"

    write_precommit(tmp_path)

    assert cfg.read_text(encoding="utf-8") == PRECOMMIT_LOCAL_HOOK_YAML


def test_write_precommit_does_not_overwrite_existing_file(
    tmp_path: Path, capsys
) -> None:
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text("already-there", encoding="utf-8")

    write_precommit(tmp_path)

    assert cfg.read_text(encoding="utf-8") == "already-there"
    out = capsys.readouterr().out
    assert "already exists" in out


def test_ensure_toolchain_exits_when_bootstrap_install_fails(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("devr.cli.run_module", lambda *_args, **_kwargs: 1)

    try:
        ensure_toolchain(tmp_path / ".venv", tmp_path)
    except Exit as exc:
        assert exc.exit_code == 1
    else:
        raise AssertionError("Expected ensure_toolchain to exit on failure")


def test_install_precommit_hook_exits_on_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("devr.cli.run_module", lambda *_args, **_kwargs: 3)

    try:
        install_precommit_hook(tmp_path / ".venv", tmp_path)
    except Exit as exc:
        assert exc.exit_code == 3
    else:
        raise AssertionError("Expected install_precommit_hook to exit on failure")


def test_init_creates_venv_when_missing(monkeypatch, tmp_path: Path) -> None:
    created: list[tuple[Path, str | None]] = []

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(venv_path=".venv"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: None)
    monkeypatch.setattr(
        "devr.cli.create_venv",
        lambda _root, venv_dir, python_exe=None: created.append((venv_dir, python_exe)),
    )
    py = tmp_path / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("", encoding="utf-8")
    monkeypatch.setattr("devr.cli.venv_python", lambda _: py)
    monkeypatch.setattr("devr.cli.ensure_toolchain", lambda *_: None)
    monkeypatch.setattr("devr.cli.install_project", lambda *_: None)
    monkeypatch.setattr("devr.cli.write_precommit", lambda *_: None)
    monkeypatch.setattr("devr.cli.install_precommit_hook", lambda *_: None)

    result = runner.invoke(app, ["init", "--python", "python3.11"])

    assert result.exit_code == 0
    assert created == [((tmp_path / ".venv").resolve(), "python3.11")]


def test_init_exits_when_venv_python_missing(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig())
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.venv_python", lambda _: tmp_path / "missing-python")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 2


def test_check_changed_staged_scopes_targets(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "c.pyi").write_text("def f() -> None: ...\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._staged_files", lambda _: ["a.py", "b.txt", "c.pyi"])

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["check", "--changed", "--staged"])

    assert result.exit_code == 0
    assert calls[0] == ("ruff", ["check", "a.py", "c.pyi"])
    assert calls[1] == ("ruff", ["format", "--check", "a.py", "c.pyi"])


def test_check_changed_uses_worktree_files_without_staged(
    monkeypatch, tmp_path: Path
) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []
    (tmp_path / "x.py").write_text("print('x')\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._changed_files", lambda _: ["x.py", "notes.md"])

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["check", "--changed"])

    assert result.exit_code == 0
    assert calls[0] == ("ruff", ["check", "x.py"])
    assert calls[1] == ("ruff", ["format", "--check", "x.py"])


def test_check_changed_skips_lint_when_no_python_files(
    monkeypatch, tmp_path: Path
) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._changed_files", lambda _: ["README.md"])

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["check", "--changed", "--fast"])

    assert result.exit_code == 0
    assert calls == []
    assert "No changed Python files detected; skipping lint/format." in result.output
    assert "No changed Python files detected; skipping type checks." in result.output


def test_check_changed_runs_pytest_when_no_python_files(
    monkeypatch, tmp_path: Path
) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "devr.cli.load_config",
        lambda _: DevrConfig(run_tests=True, coverage_branch=False, coverage_min=85),
    )
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._changed_files", lambda _: ["README.md"])
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["check", "--changed"])

    assert result.exit_code == 0
    assert calls == [
        (
            "pytest",
            ["--cov=.", "--cov-report=term-missing", "--cov-fail-under=85"],
        )
    ]


def test_check_changed_scopes_typecheck_targets(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []
    (tmp_path / "typed.py").write_text("value: int = 1\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._changed_files", lambda _: ["typed.py", "README.md"])
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["check", "--changed", "--fast"])

    assert result.exit_code == 0
    assert calls[-1] == ("mypy", ["typed.py"])


def test_check_changed_scopes_pyright_targets(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []
    (tmp_path / "typed.py").write_text("value: int = 1\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "devr.cli.load_config",
        lambda _: DevrConfig(typechecker="pyright", run_tests=False),
    )
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._changed_files", lambda _: ["typed.py"])
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["check", "--changed", "--fast"])

    assert result.exit_code == 0
    assert calls[-1] == ("pyright", ["typed.py"])


def test_check_black_formatter_paths(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "devr.cli.load_config",
        lambda _: DevrConfig(formatter="black", typechecker="pyright", run_tests=False),
    )
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert calls[0] == ("ruff", ["check", "."])
    assert calls[1] == ("black", ["-q", "--check", "."])


def test_check_exits_for_unknown_formatter(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "devr.cli.load_config",
        lambda _: DevrConfig(formatter="unknown", run_tests=False),
    )
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 2
    assert "Unknown formatter" in result.output


def test_check_exits_for_unknown_typechecker(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "devr.cli.load_config",
        lambda _: DevrConfig(typechecker="odd", run_tests=False),
    )
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli.run_module", lambda *_args, **_kwargs: 0)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 2
    assert "Unknown typechecker" in result.output


def test_check_runs_pytest_with_branch_coverage(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "devr.cli.load_config",
        lambda _: DevrConfig(coverage_branch=True, coverage_min=85),
    )
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        calls.append((module, args))
        return 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 0
    assert calls[-1] == (
        "pytest",
        ["--cov=.", "--cov-branch", "--cov-report=term-missing", "--cov-fail-under=85"],
    )


def test_check_exits_when_no_venv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig())
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: None)

    result = runner.invoke(app, ["check"])

    assert result.exit_code == 2
    assert "No venv found. Run: devr init" in result.output


def test_fix_exits_for_unknown_formatter(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(formatter="weird"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)

    result = runner.invoke(app, ["fix"])

    assert result.exit_code == 2
    assert "Unknown formatter" in result.output


def test_fix_runs_ruff_commands(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(formatter="ruff"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["fix"])

    assert result.exit_code == 0
    assert calls == [
        ("ruff", ["check", "--fix", "."]),
        ("ruff", ["format", "."]),
    ]


def test_fix_exits_when_no_venv(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig())
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: None)

    result = runner.invoke(app, ["fix"])

    assert result.exit_code == 2


def test_staged_files_returns_empty_on_git_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "devr.cli.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )

    from devr.cli import _staged_files

    assert _staged_files(tmp_path) == []


def test_staged_files_collects_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "devr.cli.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="a.py\n\n b.pyi \n"
        ),
    )

    from devr.cli import _staged_files

    assert _staged_files(tmp_path) == ["a.py", "b.pyi"]


def test_staged_files_returns_empty_when_git_is_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    def _raise(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("devr.cli.subprocess.run", _raise)

    from devr.cli import _staged_files

    assert _staged_files(tmp_path) == []


def test_changed_files_collects_tracked_and_untracked(
    monkeypatch, tmp_path: Path
) -> None:
    responses = [
        SimpleNamespace(returncode=0, stdout="a.py\na.py\nsub/b.py\n"),
        SimpleNamespace(returncode=0, stdout="new.py\n"),
    ]
    monkeypatch.setattr(
        "devr.cli.subprocess.run", lambda *args, **kwargs: responses.pop(0)
    )

    from devr.cli import _changed_files

    assert _changed_files(tmp_path) == ["a.py", "sub/b.py", "new.py"]


def test_filter_py_includes_only_python_files() -> None:
    from devr.cli import _filter_py

    assert _filter_py(["a.py", "b.pyi", "README.md"]) == ["a.py", "b.pyi"]


def test_existing_files_filters_missing_paths(tmp_path: Path) -> None:
    from devr.cli import _existing_files

    keep = tmp_path / "keep.py"
    keep.write_text("print('ok')\n", encoding="utf-8")

    assert _existing_files(tmp_path, ["keep.py", "gone.py"]) == ["keep.py"]


def test_check_changed_skips_deleted_python_files(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

    (tmp_path / "live.py").write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr("devr.cli._changed_files", lambda _: ["deleted.py", "live.py"])
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["check", "--changed", "--fast"])

    assert result.exit_code == 0
    assert calls[0] == ("ruff", ["check", "live.py"])
    assert calls[1] == ("ruff", ["format", "--check", "live.py"])


def test_check_fix_exits_when_ruff_fix_fails(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        if module == "ruff" and args == ["check", "--fix", "."]:
            return 1
        return 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["check", "--fix", "--fast"])

    assert result.exit_code == 1


def test_check_fix_changed_scopes_ruff_targets(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.pyi").write_text("def f() -> None: ...\n", encoding="utf-8")

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(run_tests=False))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)
    monkeypatch.setattr(
        "devr.cli._staged_files", lambda _: ["a.py", "notes.md", "b.pyi"]
    )
    monkeypatch.setattr(
        "devr.cli.run_module",
        lambda _venv, module, args, **_kwargs: calls.append((module, args)) or 0,
    )

    result = runner.invoke(app, ["check", "--fix", "--changed", "--staged", "--fast"])

    assert result.exit_code == 0
    assert calls[0] == ("ruff", ["check", "--fix", "a.py", "b.pyi"])
    assert calls[1] == ("ruff", ["format", "a.py", "b.pyi"])


def test_fix_exits_when_black_format_fails(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(formatter="black"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)

    def _run_module(_venv, module: str, args: list[str], **_kwargs) -> int:
        if module == "black" and args == ["."]:
            return 2
        return 0

    monkeypatch.setattr("devr.cli.run_module", _run_module)

    result = runner.invoke(app, ["fix"])

    assert result.exit_code == 2


def test_changed_files_falls_back_when_head_missing(
    monkeypatch, tmp_path: Path
) -> None:
    responses = [
        SimpleNamespace(returncode=1, stdout=""),
        SimpleNamespace(returncode=0, stdout="tracked.py\n"),
        SimpleNamespace(returncode=0, stdout="new.py\n"),
    ]
    monkeypatch.setattr(
        "devr.cli.subprocess.run", lambda *args, **kwargs: responses.pop(0)
    )

    from devr.cli import _changed_files

    assert _changed_files(tmp_path) == ["tracked.py", "new.py"]


def test_changed_files_returns_empty_when_git_is_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    def _raise(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("devr.cli.subprocess.run", _raise)

    from devr.cli import _changed_files

    assert _changed_files(tmp_path) == []


def test_project_root_prefers_nearest_pyproject(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "repo"
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        "[project]\nname='demo'\n", encoding="utf-8"
    )

    monkeypatch.chdir(nested)

    from devr.cli import project_root

    assert project_root() == project.resolve()


def test_project_root_falls_back_to_cwd_when_no_markers(
    monkeypatch, tmp_path: Path
) -> None:
    plain = tmp_path / "plain" / "nested"
    plain.mkdir(parents=True)

    monkeypatch.chdir(plain)

    from devr.cli import project_root

    assert project_root() == plain.resolve()


def test_staged_files_returns_empty_on_git_timeout(
    monkeypatch, tmp_path: Path
) -> None:
    def _raise(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr("devr.cli.subprocess.run", _raise)

    from devr.cli import _staged_files

    assert _staged_files(tmp_path) == []


def test_changed_files_returns_empty_on_git_timeout(
    monkeypatch, tmp_path: Path
) -> None:
    def _raise(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr("devr.cli.subprocess.run", _raise)

    from devr.cli import _changed_files

    assert _changed_files(tmp_path) == []
