"""Virtual environment helpers for discovering and invoking Python tools."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def is_inside_venv() -> bool:
    """Return ``True`` when the current interpreter is from an active virtual environment."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def venv_python(venv_dir: Path) -> Path:
    """Return the platform-specific Python executable path for a virtual environment."""
    windows_python = venv_dir / "Scripts" / "python.exe"
    posix_python = venv_dir / "bin" / "python"

    preferred = windows_python if os.name == "nt" else posix_python
    alternate = posix_python if os.name == "nt" else windows_python

    if preferred.exists() or not alternate.exists():
        return preferred
    return alternate


def find_venv(project_root: Path, configured: str | None) -> Path | None:
    """Locate an existing virtual environment, preferring configured and active venv paths."""
    if configured:
        p = (project_root / configured).resolve()
        if venv_python(p).exists():
            return p

    # If user is already running inside a venv, use it.
    # (Useful when devs activate venv manually.)
    if is_inside_venv():
        active = Path(sys.prefix)
        if venv_python(active).exists():
            return active

    for name in (".venv", "venv", "env"):
        p = (project_root / name).resolve()
        if venv_python(p).exists():
            return p

    return None


def create_venv(
    project_root: Path, venv_dir: Path, python_exe: str | None = None
) -> None:
    """Create a virtual environment at ``venv_dir`` using ``python_exe`` when provided."""
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    py = python_exe or sys.executable
    subprocess.check_call([py, "-m", "venv", str(venv_dir)])


def run_py(venv_dir: Path, args: list[str], cwd: Path) -> int:
    """Run Python inside ``venv_dir`` with ``args`` from ``cwd`` and return its exit code."""
    py = venv_python(venv_dir)
    return subprocess.call([py.as_posix(), *args], cwd=str(cwd))


def run_module(venv_dir: Path, module: str, args: list[str], cwd: Path) -> int:
    """Run ``python -m <module>`` inside ``venv_dir`` and return its exit code."""
    return run_py(venv_dir, ["-m", module, *args], cwd=cwd)
