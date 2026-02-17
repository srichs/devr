# devr

[![CI](https://github.com/srichs/devr/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/srichs/devr/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/devr.svg)](https://pypi.org/project/devr/)

**devr** (pronounced *dev-er*, like “developer” without the “lop”) is a single
command that runs your Python linting, formatting, type checks, tests, and
coverage inside your project’s virtual environment.

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
- `devr security [--fail-fast]`
- `devr doctor`
- `python -m devr --version` (module entrypoint smoke check)

### Shell completion

`devr` currently ships with Typer shell completion disabled (`add_completion=False`).
This is intentional for now to keep startup behavior predictable in minimal
environments and avoid implying completion-install support that is not yet
documented or validated across shells.

If you need completion today, use your shell's native completion wrappers or
aliasing as a local workaround. A future release can enable Typer completion
installation once cross-shell setup guidance is documented and tested.

### Notes

- `--changed --staged` scopes lint/format checks to staged Python files.
- `--fast` skips tests.
- `--no-tests` always skips tests, even when configured to run.
- `--fix` applies safe autofixes (ruff fix + formatting).
- `devr security` runs `pip-audit` and `bandit` for dependency and code security scans.
- `--fail-fast` stops the security scan after the first failing check.
- `devr doctor` prints environment diagnostics (project root, Python path, venv resolution, and git detection) to help debug setup issues.

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

### Virtual environment resolution order

When `devr` needs to run tooling, it resolves the venv in this order:

1. `tool.devr.venv_path` from `pyproject.toml` (when it points to a valid venv).
2. The currently active virtual environment (when `devr` is invoked from inside one).
3. Project-local fallback directories: `.venv`, then `venv`, then `env`.

This is the same resolution order used by `devr init`, `devr check`, `devr fix`, and
`devr security`.


## Release checklist

Use this checklist when cutting a release:

1. Verify local quality gates pass (`devr check` and `devr security`).
2. Update `CHANGELOG.md`:
   - Move completed entries from `Unreleased` into a new version section.
   - Add release date (`YYYY-MM-DD`) and keep entries grouped by change type.
3. Bump version in `pyproject.toml` under `[project].version`.
4. Run release preflight checks (artifact smoke tests + changelog/version consistency):
   - `python -m devr.release_preflight`
   - This builds both wheel and sdist artifacts, installs each in an isolated venv, and verifies both `devr --version` and `python -m devr --version`.
5. Commit release metadata (`CHANGELOG.md`, version bump, and any final docs updates).
6. Tag the release (for example, `vX.Y.Z`) and push branch + tag.
7. Publish to PyPI using your standard release workflow.
8. Add a fresh `Unreleased` section to `CHANGELOG.md` for subsequent work.

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
