from pathlib import Path

import pytest

from devr.release_preflight import (
    ReleasePreflightError,
    changelog_versions,
    project_version,
    validate_changelog,
)


def test_project_version_reads_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")

    assert project_version(pyproject) == "1.2.3"


def test_validate_changelog_requires_unreleased_first(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("## [0.1.0] - 2026-01-01\n", encoding="utf-8")

    with pytest.raises(ReleasePreflightError, match="Unreleased"):
        validate_changelog(changelog, "0.1.0")


def test_validate_changelog_requires_current_version_section(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "## [Unreleased]\n\n## [0.0.9] - 2026-01-01\n", encoding="utf-8"
    )

    with pytest.raises(ReleasePreflightError, match="0.1.0"):
        validate_changelog(changelog, "0.1.0")


def test_changelog_versions_extracts_headings(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "\n".join(
            [
                "# Changelog",
                "",
                "## [Unreleased]",
                "",
                "## [0.1.0] - 2026-02-17",
                "",
                "## [0.0.9] - 2026-01-10",
            ]
        ),
        encoding="utf-8",
    )

    assert changelog_versions(changelog) == ["Unreleased", "0.1.0", "0.0.9"]
