"""Configuration parsing tests for devr."""

from pathlib import Path

from devr.config import DevrConfig, load_config


def _write_pyproject(tmp_path: Path, content: str) -> None:
    (tmp_path / "pyproject.toml").write_text(content, encoding="utf-8")


def test_load_config_defaults_when_missing() -> None:
    cfg = load_config(Path("/tmp/non-existent-config-root"))
    assert cfg == DevrConfig()


def test_load_config_parses_string_booleans_and_ints(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr]
coverage_min = "90"
coverage_branch = "false"
run_tests = "true"
""",
    )

    cfg = load_config(tmp_path)

    assert cfg.coverage_min == 90
    assert cfg.coverage_branch is False
    assert cfg.run_tests is True


def test_load_config_invalid_values_fall_back_to_defaults(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr]
formatter = "flake8"
typechecker = "pyre"
coverage_min = -10
coverage_branch = "not-a-bool"
run_tests = "not-a-bool"
""",
    )

    cfg = load_config(tmp_path)
    defaults = DevrConfig()

    assert cfg.formatter == defaults.formatter
    assert cfg.typechecker == defaults.typechecker
    assert cfg.coverage_min == defaults.coverage_min
    assert cfg.coverage_branch == defaults.coverage_branch
    assert cfg.run_tests == defaults.run_tests


def test_load_config_rejects_non_binary_integer_booleans(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr]
coverage_branch = 2
run_tests = -1
""",
    )

    cfg = load_config(tmp_path)
    defaults = DevrConfig()

    assert cfg.coverage_branch == defaults.coverage_branch
    assert cfg.run_tests == defaults.run_tests


def test_load_config_rejects_boolean_for_integer_fields(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr]
coverage_min = true
""",
    )

    cfg = load_config(tmp_path)

    assert cfg.coverage_min == DevrConfig().coverage_min


def test_load_config_normalizes_string_values(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr]
venv_path = "  custom-venv  "
formatter = "RuFf"
typechecker = " PyRiGhT "
""",
    )

    cfg = load_config(tmp_path)

    assert cfg.venv_path == "custom-venv"
    assert cfg.formatter == "ruff"
    assert cfg.typechecker == "pyright"


def test_load_config_invalid_venv_path_falls_back_to_default(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr]
venv_path = "  "
""",
    )

    cfg = load_config(tmp_path)

    assert cfg.venv_path == DevrConfig().venv_path


def test_load_config_invalid_toml_falls_back_to_defaults(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        """
[tool.devr
invalid = true
""",
    )

    cfg = load_config(tmp_path)

    assert cfg == DevrConfig()
