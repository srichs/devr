# devr

[![CI](https://github.com/srichs/devr/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/srichs/devr/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/devr.svg)](https://pypi.org/project/devr/)

**devr** runs your Python dev preflight (lint, format checks, type checks, tests, and coverage)
inside your project virtual environment.

## Why devr?

- One setup command for new repos: `devr init`
- One gate command before commit/PR: `devr check`
- Works from your project venv, so tooling is isolated per repo
- Can install a local pre-commit hook that runs the same checks on staged files

Most Python projects have:
- ruff
- a formatter
- mypy or pyright
- pytest + coverage
- pre-commit

**devr runs all of them together, correctly, inside your project’s virtualenv — with one command.**

No guessing which Python is used.  
No copying long command chains.  
No drift between local and pre-commit.

---

## Install

Recommended with `pipx`:

```bash
pipx install devr
```

Or with pip:

```bash
pip install devr
```

## Quick start

From the root of a Python project:

```bash
devr init
devr check
```

`devr init` will:

1. Create or find a virtual environment.
2. Install the default toolchain into that environment.
3. Install your project dependencies (`pip install -e .` when `pyproject.toml` exists).
4. Create `.pre-commit-config.yaml` if it does not already exist.
5. Install the git pre-commit hook.

## Commands

- `devr init [--python python3.12]`
- `devr check [--fix] [--staged --changed] [--fast] [--no-tests]`
- `devr fix`
- `devr security`

### Notes

- `--changed --staged` scopes lint/format checks to staged Python files.
- `--fast` skips tests.
- `--no-tests` always skips tests, even when configured to run.
- `--fix` applies safe autofixes (ruff fix + formatting).
- `devr security` runs `pip-audit` and `bandit` for dependency and code security scans.

## Configuration

Add configuration in your `pyproject.toml`:

```toml
[tool.devr]
venv_path = ".venv"
formatter = "ruff"      # or "black"
typechecker = "mypy"    # or "pyright"
coverage_min = 85
coverage_branch = true
run_tests = true
```

If values are omitted or invalid, `devr` falls back to safe defaults.

## Default toolchain

`devr init` installs:

- `ruff`
- `black`
- `mypy`
- `pyright`
- `pytest`
- `pytest-cov`
- `pre-commit`
- `pip-audit`
- `bandit`

## License

MIT
