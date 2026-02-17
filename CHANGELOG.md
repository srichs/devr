# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added `devr doctor` for environment diagnostics and setup troubleshooting.

### Changed
- Improved `devr check` diagnostics with explicit stage headers and command summaries.
- Documented virtual environment/tooling resolution precedence in the README.
- Documented shell completion behavior and current `add_completion=False` rationale.

### Security
- Added `devr security --fail-fast` to stop on the first failing security check.

## [0.1.0] - YYYY-MM-DD

### Added
- Initial `devr` release with `init`, `check`, `fix`, and `security` commands.
- Configuration via `pyproject.toml` (`[tool.devr]`).
- Virtual-environment-aware tool execution for linting, formatting, type checks, tests, and coverage.
