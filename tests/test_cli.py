"""CLI behavior tests for devr commands."""

from pathlib import Path

from typer.testing import CliRunner

from devr.cli import app
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
