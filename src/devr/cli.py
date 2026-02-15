"""Command-line interface for running devr workflows."""

from __future__ import annotations

import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Optional

import typer

from .config import load_config
from .templates import DEFAULT_TOOLCHAIN, PRECOMMIT_LOCAL_HOOK_YAML
from .venv import create_venv, find_venv, run_module, venv_python

app = typer.Typer(
    add_completion=False,
    help="devr: run dev preflight checks inside your project venv.",
)


def _devr_version() -> str:
    """Return the installed package version or a local fallback version."""
    try:
        return version("devr")
    except PackageNotFoundError:
        return "0.0.0"


def _version_callback(value: bool) -> None:
    """Print the devr version and exit when ``--version`` is requested."""
    if value:
        typer.echo(f"devr {_devr_version()}")
        raise typer.Exit()


@app.callback()
def main(
    version_flag: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show devr version and exit.",
    ),
) -> None:
    """Define global CLI options shared by all subcommands."""
    del version_flag


def project_root() -> Path:
    """Return the current working directory as the project root."""
    # MVP: assume current working directory is project root
    return Path.cwd()


def ensure_toolchain(venv_dir: Path, root: Path) -> None:
    """Install and/or upgrade required development tools inside ``venv_dir``."""
    # Upgrade pip basics
    code = run_module(
        venv_dir, "pip", ["install", "-U", "pip", "setuptools", "wheel"], cwd=root
    )
    if code != 0:
        raise typer.Exit(code=code)
    # Install toolchain
    code = run_module(venv_dir, "pip", ["install", *DEFAULT_TOOLCHAIN], cwd=root)
    if code != 0:
        raise typer.Exit(code=code)


def install_project(venv_dir: Path, root: Path) -> None:
    """Install project dependencies from ``pyproject.toml`` or ``requirements.txt``."""
    pyproject = root / "pyproject.toml"
    reqs = root / "requirements.txt"

    if pyproject.exists():
        # Best default: editable install. If it fails, fall back to non-editable.
        code = run_module(venv_dir, "pip", ["install", "-e", "."], cwd=root)
        if code != 0:
            typer.echo(
                "Editable install failed; trying non-editable install (pip install .)"
            )
            fallback_code = run_module(venv_dir, "pip", ["install", "."], cwd=root)
            if fallback_code != 0:
                typer.echo(
                    "Warning: project install failed; continuing without installed project dependencies."
                )
        return

    if reqs.exists():
        run_module(venv_dir, "pip", ["install", "-r", "requirements.txt"], cwd=root)
        return

    typer.echo(
        "No pyproject.toml or requirements.txt found; skipping project dependency install."
    )


def write_precommit(root: Path) -> None:
    """Create the pre-commit config file when it is not already present."""
    path = root / ".pre-commit-config.yaml"
    if path.exists():
        typer.echo(".pre-commit-config.yaml already exists; leaving it unchanged.")
        typer.echo("Tip: add a local hook that runs: devr check --staged --changed")
        return
    path.write_text(PRECOMMIT_LOCAL_HOOK_YAML, encoding="utf-8")


def install_precommit_hook(venv_dir: Path, root: Path) -> None:
    """Install the local git pre-commit hook via ``pre_commit install``."""
    # Run pre-commit from inside the venv
    code = run_module(venv_dir, "pre_commit", ["install"], cwd=root)
    if code != 0:
        raise typer.Exit(code=code)


@app.command()
def init(
    python: Optional[str] = typer.Option(
        None,
        "--python",
        help="Python interpreter to use when creating the venv (e.g. python3.12).",
    ),
) -> None:
    """
    Initialize devr in this repo:
    - create/detect .venv
    - install toolchain into venv
    - install project deps (pip install -e . when pyproject.toml exists)
    - generate pre-commit config (if missing) + install hook
    """
    root = project_root()
    cfg = load_config(root)

    venv_dir = find_venv(root, cfg.venv_path)
    if venv_dir is None:
        venv_dir = (root / cfg.venv_path).resolve()
        typer.echo(f"Creating venv at: {venv_dir}")
        create_venv(root, venv_dir, python_exe=python)
    else:
        typer.echo(f"Using venv: {venv_dir}")

    py = venv_python(venv_dir)
    if not py.exists():
        raise typer.Exit(code=2)

    typer.echo("Installing dev toolchain into venv...")
    ensure_toolchain(venv_dir, root)

    typer.echo("Installing project into venv (best-effort)...")
    install_project(venv_dir, root)

    typer.echo("Setting up pre-commit...")
    write_precommit(root)
    install_precommit_hook(venv_dir, root)

    typer.echo("Done. Try: devr check")


def _staged_files(root: Path) -> list[str]:
    """Return staged file paths from git, or an empty list on command failure."""
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _changed_files(root: Path) -> list[str]:
    """Return changed and untracked file paths from git, or an empty list on failure."""
    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if tracked.returncode != 0:
        tracked = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if tracked.returncode != 0:
            return []

    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if untracked.returncode != 0:
        return []

    combined = [
        line.strip()
        for line in [*tracked.stdout.splitlines(), *untracked.stdout.splitlines()]
        if line.strip()
    ]
    return list(dict.fromkeys(combined))


def _filter_py(files: list[str]) -> list[str]:
    """Filter file paths down to Python source and typing stub files."""
    return [f for f in files if f.endswith(".py") or f.endswith(".pyi")]


def _run_or_exit(venv_dir: Path, module: str, args: list[str], root: Path) -> None:
    """Run a module command and exit with its code when the command fails."""
    code = run_module(venv_dir, module, args, cwd=root)
    if code != 0:
        raise typer.Exit(code=code)


@app.command()
def check(
    fix: bool = typer.Option(
        False, "--fix", help="Apply safe autofixes (ruff check --fix) and formatting."
    ),
    staged: bool = typer.Option(
        False, "--staged", help="Use staged files (git index) for changed-files mode."
    ),
    changed: bool = typer.Option(
        False,
        "--changed",
        help="Run on changed files only (paired with --staged recommended).",
    ),
    fast: bool = typer.Option(
        False, "--fast", help="Skip slow steps (defaults to skipping tests)."
    ),
) -> None:
    """
    Run the full preflight gate inside the project venv:
    ruff lint + format check + typecheck + pytest + coverage threshold.
    """
    root = project_root()
    cfg = load_config(root)

    venv_dir = find_venv(root, cfg.venv_path)
    if venv_dir is None:
        typer.echo("No venv found. Run: devr init")
        raise typer.Exit(code=2)

    typer.echo(f"Using venv: {venv_dir}")

    files: list[str] = []
    if changed:
        files = _filter_py(_staged_files(root) if staged else _changed_files(root))

    # 1) Format / lint
    if cfg.formatter == "ruff":
        if fix:
            fix_target = files if changed else ["."]
            if fix_target:
                _run_or_exit(venv_dir, "ruff", ["check", "--fix", *fix_target], root)
                _run_or_exit(venv_dir, "ruff", ["format", *fix_target], root)
            else:
                typer.echo("No changed Python files detected; skipping lint/format.")
        else:
            # Lint (optionally scoped)
            lint_target = files if changed else ["."]
            if lint_target:
                code = run_module(venv_dir, "ruff", ["check", *lint_target], cwd=root)
                if code != 0:
                    raise typer.Exit(code=code)
                # Format check
                code = run_module(
                    venv_dir, "ruff", ["format", "--check", *lint_target], cwd=root
                )
                if code != 0:
                    raise typer.Exit(code=code)
            else:
                typer.echo("No changed Python files detected; skipping lint/format.")
    elif cfg.formatter == "black":
        # Keep ruff lint, but black for formatting
        lint_target = files if changed else ["."]
        if lint_target:
            code = run_module(venv_dir, "ruff", ["check", *lint_target], cwd=root)
            if code != 0:
                raise typer.Exit(code=code)
            black_args = ["-q"]
            if not fix:
                black_args.append("--check")
            code = run_module(venv_dir, "black", [*black_args, *lint_target], cwd=root)
            if code != 0:
                raise typer.Exit(code=code)
        else:
            typer.echo("No changed Python files detected; skipping lint/format.")
    else:
        typer.echo(f"Unknown formatter: {cfg.formatter} (expected ruff or black)")
        raise typer.Exit(code=2)

    # 2) Type checking
    if cfg.typechecker == "mypy":
        code = run_module(venv_dir, "mypy", ["."], cwd=root)
        if code != 0:
            raise typer.Exit(code=code)
    elif cfg.typechecker == "pyright":
        code = run_module(venv_dir, "pyright", ["."], cwd=root)
        if code != 0:
            raise typer.Exit(code=code)
    else:
        typer.echo(f"Unknown typechecker: {cfg.typechecker} (expected mypy or pyright)")
        raise typer.Exit(code=2)

    # 3) Tests + coverage
    if cfg.run_tests and not fast:
        cov_args = [
            "--cov=.",
            "--cov-report=term-missing",
            f"--cov-fail-under={cfg.coverage_min}",
        ]
        if cfg.coverage_branch:
            cov_args.insert(1, "--cov-branch")
        code = run_module(venv_dir, "pytest", [*cov_args], cwd=root)
        if code != 0:
            raise typer.Exit(code=code)

    typer.echo("✅ devr check passed")


@app.command()
def fix() -> None:
    """Apply configured lint fixes and formatting in the active project venv."""
    root = project_root()
    cfg = load_config(root)
    venv_dir = find_venv(root, cfg.venv_path)
    if venv_dir is None:
        typer.echo("No venv found. Run: devr init")
        raise typer.Exit(code=2)

    if cfg.formatter == "ruff":
        _run_or_exit(venv_dir, "ruff", ["check", "--fix", "."], root)
        _run_or_exit(venv_dir, "ruff", ["format", "."], root)
    elif cfg.formatter == "black":
        _run_or_exit(venv_dir, "ruff", ["check", "--fix", "."], root)
        _run_or_exit(venv_dir, "black", ["."], root)
    else:
        typer.echo(f"Unknown formatter: {cfg.formatter}")
        raise typer.Exit(code=2)

    typer.echo("✅ devr fix complete")


@app.command()
def security() -> None:
    """Run dependency and static-analysis security checks in the project venv."""
    root = project_root()
    cfg = load_config(root)
    venv_dir = find_venv(root, cfg.venv_path)
    if venv_dir is None:
        typer.echo("No venv found. Run: devr init")
        raise typer.Exit(code=2)

    typer.echo(f"Using venv: {venv_dir}")

    code = run_module(venv_dir, "pip_audit", [], cwd=root)
    if code != 0:
        raise typer.Exit(code=code)

    code = run_module(venv_dir, "bandit", ["-r", ".", "-x", cfg.venv_path], cwd=root)
    if code != 0:
        raise typer.Exit(code=code)

    typer.echo("✅ devr security passed")
