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
