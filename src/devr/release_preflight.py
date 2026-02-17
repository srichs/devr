"""Release preflight checks for packaging and changelog consistency."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on older runtimes
    import tomli as tomllib


REPO_ROOT = Path(__file__).resolve().parents[2]


class ReleasePreflightError(RuntimeError):
    """Raised when a release preflight check fails."""


def project_version(pyproject_path: Path) -> str:
    """Return the ``[project].version`` from ``pyproject.toml``."""
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise ReleasePreflightError(
            "Could not determine [project].version from pyproject.toml"
        )
    return version.strip()


def changelog_versions(changelog_path: Path) -> list[str]:
    """Return version labels from markdown changelog headings."""
    versions: list[str] = []
    pattern = re.compile(r"^## \[(.+?)\]")
    for line in changelog_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line.strip())
        if match:
            versions.append(match.group(1))
    return versions


def validate_changelog(changelog_path: Path, version: str) -> None:
    """Validate changelog has expected release structure for ``version``."""
    changelog_text = changelog_path.read_text(encoding="utf-8")
    versions = changelog_versions(changelog_path)
    if not versions or versions[0] != "Unreleased":
        raise ReleasePreflightError(
            "CHANGELOG.md must have '## [Unreleased]' as the first section"
        )
    if version not in versions:
        raise ReleasePreflightError(
            f"CHANGELOG.md is missing a section for version {version!r}. "
            "Move completed entries from Unreleased into that release section before tagging."
        )

    unreleased_match = re.search(
        r"^## \[Unreleased\]\s*(.*?)(?=^## \[|\Z)",
        changelog_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if unreleased_match and unreleased_match.group(1).strip():
        raise ReleasePreflightError(
            "CHANGELOG.md has unreleased entries. Move completed entries from "
            "'Unreleased' into the current version section before tagging."
        )


def run_checked(cmd: list[str], cwd: Path) -> None:
    """Run command and fail with a clear message on non-zero exit."""
    print(f"$ {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise ReleasePreflightError(
            f"Command failed with exit code {completed.returncode}: {' '.join(cmd)}"
        )


def artifact_path(dist_dir: Path, suffix: str) -> Path:
    """Return the first dist artifact matching a suffix."""
    matches = sorted(dist_dir.glob(f"*{suffix}"))
    if not matches:
        raise ReleasePreflightError(f"No {suffix} artifact found in {dist_dir}")
    return matches[0]


def smoke_test_artifact(artifact: Path, repo_root: Path) -> None:
    """Install an artifact in a temporary venv and run version entrypoint checks."""
    with tempfile.TemporaryDirectory(prefix="devr-release-") as tmp:
        venv_dir = Path(tmp) / ".venv"
        python_bin = venv_dir / (
            "Scripts/python.exe" if sys.platform.startswith("win") else "bin/python"
        )
        run_checked([sys.executable, "-m", "venv", str(venv_dir)], cwd=repo_root)
        run_checked(
            [str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], cwd=repo_root
        )
        run_checked(
            [
                str(python_bin),
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                str(artifact),
            ],
            cwd=repo_root,
        )
        run_checked([str(python_bin), "-m", "devr", "--version"], cwd=repo_root)
        run_checked([str(python_bin), "-m", "pip", "show", "devr"], cwd=repo_root)
        scripts_dir = python_bin.parent
        devr_bin = scripts_dir / (
            "devr.exe" if sys.platform.startswith("win") else "devr"
        )
        run_checked([str(devr_bin), "--version"], cwd=repo_root)


def main() -> int:
    """Run release preflight checks for changelog, artifacts, and entrypoints."""
    repo_root = REPO_ROOT
    pyproject_path = repo_root / "pyproject.toml"
    changelog_path = repo_root / "CHANGELOG.md"
    dist_dir = repo_root / "dist"

    version = project_version(pyproject_path)
    print(f"Detected project version: {version}")
    validate_changelog(changelog_path, version)
    print("Changelog/version check passed.")

    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    run_checked([sys.executable, "-m", "build", "--version"], cwd=repo_root)
    run_checked([sys.executable, "-m", "build"], cwd=repo_root)

    wheel = artifact_path(dist_dir, ".whl")
    sdist = artifact_path(dist_dir, ".tar.gz")

    print(f"Smoke testing wheel artifact: {wheel.name}")
    smoke_test_artifact(wheel, repo_root)
    print(f"Smoke testing sdist artifact: {sdist.name}")
    smoke_test_artifact(sdist, repo_root)

    print("Release preflight checks completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
