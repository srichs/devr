from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def is_inside_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def find_venv(project_root: Path, configured: str | None) -> Path | None:
    if configured:
        p = (project_root / configured).resolve()
        if venv_python(p).exists():
            return p

    # If user is already running inside a venv, use it.
    # (Useful when devs activate venv manually.)
    if is_inside_venv():
        return Path(sys.prefix)

    for name in (".venv", "venv", "env"):
        p = (project_root / name).resolve()
        if venv_python(p).exists():
            return p

    return None


def create_venv(project_root: Path, venv_dir: Path, python_exe: str | None = None) -> None:
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    py = python_exe or sys.executable
    subprocess.check_call([py, "-m", "venv", str(venv_dir)])


def run_py(venv_dir: Path, args: list[str], cwd: Path) -> int:
    py = venv_python(venv_dir)
    return subprocess.call([str(py), *args], cwd=str(cwd))


def run_module(venv_dir: Path, module: str, args: list[str], cwd: Path) -> int:
    return run_py(venv_dir, ["-m", module, *args], cwd=cwd)
