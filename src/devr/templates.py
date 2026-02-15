"""Template values used by the CLI bootstrap commands."""

from __future__ import annotations

DEFAULT_TOOLCHAIN = [
    "ruff>=0.6",
    "pytest>=8",
    "pytest-cov>=5",
    "mypy>=1.10",
    "pyright>=1.1.380",
    "pre-commit>=3.7",
    "pip-audit>=2.7",
    "bandit>=1.7",
    "black>=24.8",
]

PRECOMMIT_LOCAL_HOOK_YAML = """\
repos:
  - repo: local
    hooks:
      - id: devr-check
        name: devr check (staged)
        entry: devr check --staged --changed
        language: system
        pass_filenames: false
"""
