"""CLI behavior tests for devr commands."""

from pathlib import Path

from importlib.metadata import PackageNotFoundError

from typer.testing import CliRunner

from devr.cli import app, install_project, write_precommit
from devr.config import DevrConfig

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
    assert calls == [("pip_audit", []), ("bandit", ["-r", ".", "-x", ".venv"])]
    assert "✅ devr security passed" in result.output


def test_devr_version_falls_back_when_package_not_installed(monkeypatch) -> None:
    def _raise(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr("devr.cli.version", _raise)

    from devr.cli import _devr_version

    assert _devr_version() == "0.0.0"


def test_install_project_falls_back_to_non_editable(monkeypatch, tmp_path: Path) -> None:
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


def test_install_project_skips_when_no_dependency_file(tmp_path: Path, capsys) -> None:
    install_project(tmp_path / ".venv", tmp_path)

    out = capsys.readouterr().out
    assert "No pyproject.toml or requirements.txt found" in out


def test_write_precommit_does_not_overwrite_existing_file(tmp_path: Path, capsys) -> None:
    cfg = tmp_path / ".pre-commit-config.yaml"
    cfg.write_text("already-there", encoding="utf-8")

    write_precommit(tmp_path)

    assert cfg.read_text(encoding="utf-8") == "already-there"
    out = capsys.readouterr().out
    assert "already exists" in out


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


def test_check_changed_staged_scopes_targets(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()
    calls: list[tuple[str, list[str]]] = []

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


def test_fix_exits_for_unknown_formatter(monkeypatch, tmp_path: Path) -> None:
    venv_path = (tmp_path / ".venv").resolve()

    monkeypatch.setattr("devr.cli.project_root", lambda: tmp_path)
    monkeypatch.setattr("devr.cli.load_config", lambda _: DevrConfig(formatter="weird"))
    monkeypatch.setattr("devr.cli.find_venv", lambda *_: venv_path)

    result = runner.invoke(app, ["fix"])

    assert result.exit_code == 2
    assert "Unknown formatter" in result.output
