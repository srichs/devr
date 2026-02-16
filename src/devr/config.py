"""Configuration loading and normalization for ``[tool.devr]`` settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib  # py311+  # type: ignore
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

TOMLDecodeError = getattr(tomllib, "TOMLDecodeError", ValueError)


@dataclass(frozen=True)
class DevrConfig:
    """Validated runtime configuration for devr commands."""

    venv_path: str = ".venv"
    formatter: str = "ruff"  # "ruff" | "black"
    typechecker: str = "mypy"  # "mypy" | "pyright"
    coverage_min: int = 85
    coverage_branch: bool = True
    run_tests: bool = True


def _parse_bool(value: Any, default: bool) -> bool:
    """Parse a permissive boolean value, returning ``default`` when invalid."""
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
        if value in {0, 1}:
            return bool(value)
        return default
    return default


def _parse_int(
    value: Any,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    """Parse an integer and enforce optional inclusive min and max bounds."""
    if isinstance(value, bool):
        return default

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
    """Normalize and validate a string selection against ``allowed`` choices."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in allowed:
            return normalized
    return default


def _parse_venv_path(value: Any, default: str) -> str:
    """Parse the configured venv path and fall back when it is blank or invalid."""
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return default


def load_config(project_root: Path) -> DevrConfig:
    """Load ``[tool.devr]`` from ``pyproject.toml`` and return a validated config object."""
    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        return DevrConfig()

    data: dict[str, Any]
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except TOMLDecodeError:
        return DevrConfig()

    tool = data.get("tool", {})
    devr = tool.get("devr", {}) if isinstance(tool, dict) else {}
    if not isinstance(devr, dict):
        return DevrConfig()

    base = DevrConfig()
    return DevrConfig(
        venv_path=_parse_venv_path(devr.get("venv_path"), base.venv_path),
        formatter=_parse_choice(
            devr.get("formatter"), base.formatter, allowed={"ruff", "black"}
        ),
        typechecker=_parse_choice(
            devr.get("typechecker"), base.typechecker, allowed={"mypy", "pyright"}
        ),
        coverage_min=_parse_int(
            devr.get("coverage_min"), base.coverage_min, min_value=0, max_value=100
        ),
        coverage_branch=_parse_bool(devr.get("coverage_branch"), base.coverage_branch),
        run_tests=_parse_bool(devr.get("run_tests"), base.run_tests),
    )
