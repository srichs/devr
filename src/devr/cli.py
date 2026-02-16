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
    """Return the nearest ancestor directory that looks like a project root."""
    cwd = Path.cwd().resolve()

    for candidate in (cwd, *cwd.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate

    return cwd


def _warn_if_venv_path_outside_root(root: Path, configured_venv_path: str) -> None:
    """Warn when configured venv path resolves outside the current project root."""
    configured_path = Path(configured_venv_path).expanduser()
    resolved = (
        configured_path.resolve()
        if configured_path.is_absolute()
        else (root / configured_path).resolve()
    )
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        typer.echo(
            f"Warning: configured venv_path '{configured_venv_path}' resolves outside project root ({root})."
        )


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
        code = run_module(
            venv_dir, "pip", ["install", "-r", "requirements.txt"], cwd=root
        )
        if code != 0:
            typer.echo(
                "Warning: requirements install failed; continuing without installed project dependencies."
            )
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
    if _run_git(root, ["rev-parse", "--is-inside-work-tree"]) is None:
        typer.echo("No git repository found; skipping pre-commit hook install.")
        return

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
    _warn_if_venv_path_outside_root(root, cfg.venv_path)

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
    proc = _run_git(root, ["diff", "--name-only", "--cached"])
    if proc is None:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a git command and return the completed process when successful."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc


def _is_git_repo(root: Path, cache: Optional[dict[str, bool]] = None) -> bool:
    """Return whether ``root`` is inside a git work tree, with optional caching."""
    cache_key = str(root.resolve())
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    inside_work_tree = (
        _run_git(root, ["rev-parse", "--is-inside-work-tree"]) is not None
    )
    if cache is not None:
        cache[cache_key] = inside_work_tree
    return inside_work_tree


def _changed_files(
    root: Path, git_repo_cache: Optional[dict[str, bool]] = None
) -> list[str]:
    """Return changed and untracked file paths from git, or an empty list on failure."""
    tracked = _run_git(root, ["diff", "--name-only", "HEAD"])
    if tracked is None:
        unstaged = _run_git(root, ["diff", "--name-only"])
        staged = _run_git(root, ["diff", "--name-only", "--cached"])
        if unstaged is None and staged is None:
            return []
        fallback_lines = []
        if unstaged is not None:
            fallback_lines.extend(unstaged.stdout.splitlines())
        if staged is not None:
            fallback_lines.extend(staged.stdout.splitlines())
        tracked_lines = [line.strip() for line in fallback_lines if line.strip()]
    else:
        tracked_lines = tracked.stdout.splitlines()

    if not tracked_lines and not _is_git_repo(root, git_repo_cache):
        return []

    untracked = _run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked is None:
        untracked_lines: list[str] = []
    else:
        untracked_lines = untracked.stdout.splitlines()

    combined = [
        line.strip() for line in [*tracked_lines, *untracked_lines] if line.strip()
    ]
    return list(dict.fromkeys(combined))


def _filter_py(files: list[str]) -> list[str]:
    """Filter file paths down to Python source and typing stub files."""
    return [f for f in files if f.endswith(".py") or f.endswith(".pyi")]


def _existing_files(root: Path, files: list[str]) -> list[str]:
    """Return only file paths that currently exist under ``root``."""
    root_resolved = root.resolve()
    existing: list[str] = []
    for file in files:
        candidate = Path(file)
        path = candidate if candidate.is_absolute() else root / candidate
        try:
            resolved = path.resolve()
            resolved.relative_to(root_resolved)
        except ValueError:
            continue

        if resolved.is_file():
            existing.append(file)
    return existing


def _run_or_exit(venv_dir: Path, module: str, args: list[str], root: Path) -> None:
    """Run a module command and exit with its code when the command fails."""
    code = _run_with_summary(venv_dir, module, args, root)
    if code != 0:
        raise typer.Exit(code=code)


def _run_with_summary(venv_dir: Path, module: str, args: list[str], root: Path) -> int:
    """Print a short command summary and execute the module."""
    typer.echo(f"Running: {module} {' '.join(args)}")
    return run_module(venv_dir, module, args, cwd=root)


def _run_check_stage(
    venv_dir: Path,
    module: str,
    args: list[str],
    root: Path,
    stage_name: str,
) -> int:
    """Print a check-stage header, then execute the command."""
    typer.echo(f"Stage: {stage_name}")
    return _run_with_summary(venv_dir, module, args, root)


def _typecheck_targets(changed: bool, files: list[str]) -> list[str]:
    """Return type-check targets, scoping to changed files when requested."""
    if not changed:
        return ["."]
    return files


def _bandit_excludes(root: Path, configured_venv_path: str, venv_dir: Path) -> str:
    """Build a comma-separated exclusion list for bandit scans."""

    def _normalize_exclude_path(value: str) -> str:
        """Normalize exclusion paths for stable, cross-platform bandit args."""
        normalized = value.strip().replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized.rstrip("/")

    excludes: list[str] = [
        _normalize_exclude_path(configured_venv_path),
        ".venv",
        "venv",
        "env",
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "build",
        "dist",
    ]
    try:
        rel_venv = venv_dir.resolve().relative_to(root.resolve())
        excludes.append(_normalize_exclude_path(rel_venv.as_posix()))
    except ValueError:
        # Active environment can be outside the project root; keep default exclusions.
        pass

    return ",".join(dict.fromkeys(excludes))


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
    no_tests: bool = typer.Option(
        False, "--no-tests", help="Skip running tests regardless of config settings."
    ),
) -> None:
    """
    Run the full preflight gate inside the project venv:
    ruff lint + format check + typecheck + pytest + coverage threshold.
    """
    root = project_root()
    cfg = load_config(root)
    _warn_if_venv_path_outside_root(root, cfg.venv_path)

    if staged and not changed:
        typer.echo("Warning: --staged has no effect without --changed.")

    venv_dir = find_venv(root, cfg.venv_path)
    if venv_dir is None:
        typer.echo("No venv found. Run: devr init")
        raise typer.Exit(code=2)

    typer.echo(f"Using venv: {venv_dir}")

    git_repo_cache: dict[str, bool] = {}

    files: list[str] = []
    if changed:
        changed_candidates = (
            _staged_files(root) if staged else _changed_files(root, git_repo_cache)
        )
        files = _existing_files(root, _filter_py(changed_candidates))
        if not changed_candidates and not _is_git_repo(root, git_repo_cache):
            typer.echo(
                "Warning: unable to read git state; --changed mode found no file targets."
            )

    # 1) Format / lint
    if cfg.formatter == "ruff":
        if fix:
            fix_target = files if changed else ["."]
            if fix_target:
                code = _run_check_stage(
                    venv_dir,
                    "ruff",
                    ["check", "--fix", *fix_target],
                    root,
                    "ruff check --fix",
                )
                if code != 0:
                    raise typer.Exit(code=code)

                code = _run_check_stage(
                    venv_dir,
                    "ruff",
                    ["format", *fix_target],
                    root,
                    "ruff format",
                )
                if code != 0:
                    raise typer.Exit(code=code)
            else:
                typer.echo("No changed Python files detected; skipping lint/format.")
        else:
            # Lint (optionally scoped)
            lint_target = files if changed else ["."]
            if lint_target:
                code = _run_check_stage(
                    venv_dir,
                    "ruff",
                    ["check", *lint_target],
                    root,
                    "ruff check",
                )
                if code != 0:
                    raise typer.Exit(code=code)
                # Format check
                code = _run_check_stage(
                    venv_dir,
                    "ruff",
                    ["format", "--check", *lint_target],
                    root,
                    "ruff format --check",
                )
                if code != 0:
                    raise typer.Exit(code=code)
            else:
                typer.echo("No changed Python files detected; skipping lint/format.")
    elif cfg.formatter == "black":
        # Keep ruff lint, but black for formatting
        lint_target = files if changed else ["."]
        if lint_target:
            code = _run_check_stage(
                venv_dir,
                "ruff",
                ["check", *lint_target],
                root,
                "ruff check",
            )
            if code != 0:
                raise typer.Exit(code=code)
            black_args = ["-q"]
            if not fix:
                black_args.append("--check")
            stage_name = "black" if fix else "black --check"
            code = _run_check_stage(
                venv_dir,
                "black",
                [*black_args, *lint_target],
                root,
                stage_name,
            )
            if code != 0:
                raise typer.Exit(code=code)
        else:
            typer.echo("No changed Python files detected; skipping lint/format.")
    else:
        typer.echo(f"Unknown formatter: {cfg.formatter} (expected ruff or black)")
        raise typer.Exit(code=2)

    # 2) Type checking
    typecheck_target = _typecheck_targets(changed, files)
    if not typecheck_target:
        typer.echo("No changed Python files detected; skipping type checks.")
    else:
        if cfg.typechecker == "mypy":
            code = _run_check_stage(
                venv_dir,
                "mypy",
                typecheck_target,
                root,
                "mypy",
            )
            if code != 0:
                raise typer.Exit(code=code)
        elif cfg.typechecker == "pyright":
            code = _run_check_stage(
                venv_dir,
                "pyright",
                typecheck_target,
                root,
                "pyright",
            )
            if code != 0:
                raise typer.Exit(code=code)
        else:
            typer.echo(
                f"Unknown typechecker: {cfg.typechecker} (expected mypy or pyright)"
            )
            raise typer.Exit(code=2)

    # 3) Tests + coverage
    if cfg.run_tests and not fast and not no_tests:
        cov_args = [
            "--cov=.",
            "--cov-report=term-missing",
            f"--cov-fail-under={cfg.coverage_min}",
        ]
        if cfg.coverage_branch:
            cov_args.insert(1, "--cov-branch")
        code = _run_check_stage(
            venv_dir,
            "pytest",
            [*cov_args],
            root,
            "pytest",
        )
        if code != 0:
            raise typer.Exit(code=code)
    elif no_tests:
        typer.echo("Skipping tests (--no-tests).")
    elif fast:
        typer.echo("Skipping tests (--fast).")

    typer.echo("✅ devr check passed")


@app.command()
def fix() -> None:
    """Apply configured lint fixes and formatting in the active project venv."""
    root = project_root()
    cfg = load_config(root)
    _warn_if_venv_path_outside_root(root, cfg.venv_path)
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
def security(
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast",
        help="Exit after the first failing security check.",
    ),
) -> None:
    """Run dependency and static-analysis security checks in the project venv."""
    root = project_root()
    cfg = load_config(root)
    _warn_if_venv_path_outside_root(root, cfg.venv_path)
    venv_dir = find_venv(root, cfg.venv_path)
    if venv_dir is None:
        typer.echo("No venv found. Run: devr init")
        raise typer.Exit(code=2)

    typer.echo(f"Using venv: {venv_dir}")

    pip_audit_code = _run_with_summary(venv_dir, "pip_audit", [], root)
    if pip_audit_code != 0 and fail_fast:
        typer.echo("Security checks failed: pip-audit")
        raise typer.Exit(code=1)

    bandit_code = _run_with_summary(
        venv_dir,
        "bandit",
        ["-r", ".", "-x", _bandit_excludes(root, cfg.venv_path, venv_dir)],
        root,
    )
    if bandit_code != 0 and fail_fast:
        typer.echo("Security checks failed: bandit")
        raise typer.Exit(code=1)

    failed_checks: list[str] = []
    if pip_audit_code != 0:
        failed_checks.append("pip-audit")
    if bandit_code != 0:
        failed_checks.append("bandit")
    if failed_checks:
        typer.echo(f"Security checks failed: {', '.join(failed_checks)}")
        raise typer.Exit(code=1)

    typer.echo("✅ devr security passed")
