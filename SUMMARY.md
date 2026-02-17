# devr: Python Developer Tooling Suite

**What it is / Who it's for:**

`devr` is a CLI tool for Python developers/projects that automates and unifies code quality (lint/format/typecheck/test/coverage) and security gates inside a project's virtual environment (venv). It's designed for both solo and team use, aiming for reproducible and reliable dev/test quality checks tied to a project's venv and configuration.

---

## Key Features (from code evidence)
- **Unified, reliable preflight checks**: `devr check` runs lint (ruff), formatting (ruff/black), type checks (mypy/pyright), tests (pytest), coverage, and security (security via `devr security`) all inside the project venv.
- **Automated onboarding/setup** (`devr init`): Idempotently creates/fixes venv, installs toolchain dependencies (upgrade pip/setuptools/wheel, install ruff, mypy, pytest, etc.), installs project deps (first tries `pip install -e .`, falls back to `pip install .`), optionally requirements.txt. Generates `.pre-commit-config.yaml` if missing and installs pre-commit hook if in a git repo.
- **Pre-commit local hook integration**: Generates self-updating pre-commit hook YAML if needed and ensures sync between local and pre-commit checks.
- **Project-local venv/tooling**: All tool executions run via the selected venv (configurable in `[tool.devr]`), never global Python.
- **Selective, scoped checks**: `--changed`, `--staged`, `--fix`, `--fast`, `--no-tests` allow checks to target changed/staged files, skip slow steps, or force skips.
- **Config via `pyproject.toml`:**
  - `venv_path`, `formatter` ("ruff"/"black"), `typechecker` ("mypy"/"pyright"), `coverage_min`, `coverage_branch`, `run_tests`
- **Doctor/diagnostics** (`devr doctor`): Prints venv/config/git/project status and hints when things are wrong.
- **Security checks**: `devr security` runs `pip-audit` and `bandit` (with aggressive auto-excludes for venv, cache, .git, etc). Failures surface clearly; `--fail-fast` stops at first.
- **Release preflight**: (Implied; likely via `release_preflight.py`).
- **CLI via Typer**: Provides standard CLI help, usage, and argument parsing (shell completion intentionally disabled).
- **Tests:** Pytest-based suite with CLI integration/edge-cases covered (`tests/test_cli.py`).

## Architecture & Execution Model
- **Entrypoint:**
  - Via command line: `devr ...` (setuptools-exposed script)
  - As a module: `python -m devr ...`
- **Major modules:**
  - `src/devr/cli.py`: Entrypoint, CLI logic, orchestration, command run graphing, venv/file/project root detection, argument parsing.
  - `src/devr/config.py`: Loads and validates settings from `pyproject.toml` (`[tool.devr]`), robust fallbacks.
  - `src/devr/venv.py`: venv detection, creation, "active venv" fallback if the user is already in a venv, and tool invocation.
- **Test evidence** (`tests/test_cli.py`): Verifies all command-line behaviors, error handling, config edge cases, venv/project/dep install path handling, file scoping logic, YAML output, pre-commit logic, and security check orchestration. Coverage for both success and failure cases.

## Supported Toolchain (per code)
- **Formatter:** Ruff (default) or Black
- **Linter:** Ruff
- **Type checker:** Mypy (default) or Pyright
- **Test runner:** Pytest
- **Coverage:** Pytest-cov/coverage (thresholds enforced via config)
- **Security:** pip-audit, bandit

## Config / Env Vars
- **Config:**
  - Only via `[tool.devr]` in `pyproject.toml`. No direct env var support in code.
  ```toml
  [tool.devr]
  venv_path = ".venv"
  formatter = "ruff"      # or "black"
  typechecker = "mypy"    # or "pyright"
  coverage_min = 85
  coverage_branch = true
  run_tests = true
  ```

## Extension/Plug-in Model
- **NOT supported:** There is no evidence in the CLI or config code for custom user tool integration, plugins, or hooks beyond selectable formatter/typechecker. The toolchain is extensible mainly by adjusting defaults and configuration of existing tools, not by adding arbitrary new commands.

## Data Flow
- **Local-only:** Invokes tools via subprocess inside the selected venv.
- **No APIs/DBs**: Reads/writes only local files and venv directory. Uses git for file scoping and hook installation.

## Known Limitations / Gotchas (evidence-based)
- **Shell completion** is disabled (see Typer configuration).
- **Venv path**: User can misconfigure a venv path outside project root; warning shown, but tools may not run correctly.
- **No extension/plugin API**.
- **Only one tool per role (formatter/typechecker) can be chosen via config.**
- **Cross-platform**: All logic is guarded for Windows/Unix, but some assumptions (such as posix python path logic or pip install behaviors) could have platform edge-cases, especially in nonstandard VCS/project layouts.
- **Relies on git:** Selective checks require a git repository; if not present or git state unreadable, falls back gracefully.
- **Best effort dep install**: `devr init` will attempt editable project install, fall back to non-editable, then fallback to requirements.txt. If all fail, it prints warnings.
- **Security excludes**: Bandit gets a dynamic exclude list for venv directories, git, caches, etc. based on resolved paths.

## Verified by test evidence
- All major CLI behaviors, fallback logic, git integration, venv creation/detection, toolchain install, security handling, and error modes are exercised by tests in `tests/test_cli.py`.

---

## Where to Start in the Codebase
1. **src/devr/cli.py** — central CLI and platform orchestration logic
2. **src/devr/config.py** — configuration loading and normalization
3. **src/devr/venv.py** — virtual environment discovery, creation, and execution logic

## Open Questions
- No support for user-pluggable custom tools (evidenced in config and CLI parsing). To add such support would require core code changes.
- Hooks/extensions: None present; not a plug-in platform.
- Cross-platform bugs: Most paths are handled as Path objects and cross-checked, but a user with unusual layouts/permissions may still need to review venv detection logic for edge cases.

---

## Supported by code evidence
- All claims about commands, execution paths, config options, venv/tool install, test handling, and security integrations.
- Extensibility (custom tools/plugins) is **not** supported beyond builtin choice toggles for formatter/typechecker.

## Immediate 80% summary
*devr* is a reliable, extensible-for-most, but not pluggable, Python CLI suite for unified local dev quality/security gates with a heavy focus on reproducibility and venv isolation — good for individuals and teams wanting consistent, project-local preflight automation.


# Reading plan

This plan will help you become productive quickly with the `devr` Python Developer Tooling Suite. By following the sequence, you'll understand the CLI surface, core architecture, configuration, virtual environment handling, and how to test/make safe changes.

## Ordered Reading Plan

1. **README.md**
   *Why it matters:* Provides high-level overview, usage examples, and key features.
   *What to look for:*
   - What `devr` does and its intended workflow
   - Key commands and their purpose
   - Any project-specific setup notes
   *Time estimate:* 8 min

2. **pyproject.toml**
   *Why it matters:* Holds all configuration (`[tool.devr]`) and project metadata.
   *What to look for:*
   - `[tool.devr]` config options and meanings
   - Toolchain dependencies for install
   *Time estimate:* 5 min

3. **src/devr/cli.py**
   *Why it matters:* Main CLI entrypoint; orchestrates commands, argument parsing, and flow.
   *What to look for:*
   - How commands map to underlying quality/security/test actions
   - Logic for check/init/security/subcommands
   - Project/venv/file scoping logic
   *Time estimate:* 15 min

4. **src/devr/config.py**
   *Why it matters:* Loads and validates config from `pyproject.toml`.
   *What to look for:*
   - How config options are loaded, validated, and defaulted
   - Fallback logic for missing or partial configs
   *Time estimate:* 10 min

5. **src/devr/venv.py**
   *Why it matters:* Responsible for virtual environment detection, creation, and subprocess execution.
   *What to look for:*
   - How venvs are found, instantiated, and confirmed as 'active'
   - Tool invocation and isolation strategy
   *Time estimate:* 10 min

6. **src/devr/release_preflight.py**
   *Why it matters:* (If present) Automates release-time checks—good example of composite health/pre-releasing logic.
   *What to look for:*
   - Steps performed during pre-release
   - Any additional gates or validation logic for publishing
   *Time estimate:* 7 min

7. **src/devr/templates.py**
   *Why it matters:* Provides pre-commit and related hook templates, important for how automated hooks integrate.
   *What to look for:*
   - The content generated for pre-commit hooks/config
   - How templates are kept up-to-date or modified on `init`
   *Time estimate:* 5 min

8. **tests/test_cli.py**
   *Why it matters:* Main test suite covering the CLI; offers concrete examples and edge cases.
   *What to look for:*
   - How CLI behavior is asserted (success/failure, config, install, edge cases)
   - How venv interactions and file scoping are exercised
   *Time estimate:* 8 min

9. **tests/test_venv.py**
   *Why it matters:* Tests venv detection/creation/execution; ensures you understand venv-related failure/success paths.
   *What to look for:*
   - Venv error handling and path edge-case testing
   *Time estimate:* 5 min

10. **tests/test_cli_integration.py**
    *Why it matters:* Asserts integration between CLI and actual subprocess execution.
    *What to look for:*
    - Realistic flows that touch venv, config, and command hooks together
    *Time estimate:* 5 min


## If you only have 30 minutes
1. **README.md** (skim for big-picture usage and features)
2. **src/devr/cli.py** (skim top-level command mapping, main orchestration, and key function/class signatures)
3. **pyproject.toml** (skim `[tool.devr]` config block, look for main toggles and options)


## If you need to make a change safely
- **How to run tests/build:**
  - `pytest` in project root (all main test code is under `tests/`) will run the suite and cover CLI, venv, config, and integration.
- **Where to add a small change and validate quickly:**
  - Small CLI tweaks: `src/devr/cli.py` (for new logic or argument tweaks)
  - Config parsing/default changes: `src/devr/config.py`
  - Venv/tool invocation: `src/devr/venv.py`
  - After change, validate with `pytest tests/test_cli.py` and, if venv-related, also `pytest tests/test_venv.py`