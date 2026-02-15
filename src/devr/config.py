from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # py311+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass(frozen=True)
class DevrConfig:
    venv_path: str = ".venv"
    formatter: str = "ruff"  # "ruff" | "black"
    typechecker: str = "mypy"  # "mypy" | "pyright"
    coverage_min: int = 85
    coverage_branch: bool = True
    run_tests: bool = True


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default
    if isinstance(value, int):
        return bool(value)
    return default


def _parse_int(value: Any, default: int, *, min_value: int | None = None, max_value: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default

    if min_value is not None and parsed < min_value:
        return default
    if max_value is not None and parsed > max_value:
        return default
    return parsed


def _parse_choice(value: Any, default: str, *, allowed: set[str]) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in allowed:
            return normalized
    return default


def _parse_venv_path(value: Any, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return default


def load_config(project_root: Path) -> DevrConfig:
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return DevrConfig()

    data: dict[str, Any]
    with pyproject.open("rb") as f:
        data = tomllib.load(f)

    tool = data.get("tool", {})
    devr = tool.get("devr", {}) if isinstance(tool, dict) else {}
    if not isinstance(devr, dict):
        return DevrConfig()

    base = DevrConfig()
    return DevrConfig(
        venv_path=_parse_venv_path(devr.get("venv_path"), base.venv_path),
        formatter=_parse_choice(devr.get("formatter"), base.formatter, allowed={"ruff", "black"}),
        typechecker=_parse_choice(devr.get("typechecker"), base.typechecker, allowed={"mypy", "pyright"}),
        coverage_min=_parse_int(devr.get("coverage_min"), base.coverage_min, min_value=0, max_value=100),
        coverage_branch=_parse_bool(devr.get("coverage_branch"), base.coverage_branch),
        run_tests=_parse_bool(devr.get("run_tests"), base.run_tests),
    )
