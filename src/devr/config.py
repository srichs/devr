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
    formatter: str = "ruff"      # "ruff" | "black"
    typechecker: str = "mypy"    # "mypy" | "pyright"
    coverage_min: int = 85
    coverage_branch: bool = True
    run_tests: bool = True


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
        venv_path=str(devr.get("venv_path", base.venv_path)),
        formatter=str(devr.get("formatter", base.formatter)),
        typechecker=str(devr.get("typechecker", base.typechecker)),
        coverage_min=int(devr.get("coverage_min", base.coverage_min)),
        coverage_branch=bool(devr.get("coverage_branch", base.coverage_branch)),
        run_tests=bool(devr.get("run_tests", base.run_tests)),
    )
