# Project Review: Next Improvement Opportunities

This review was refreshed after the latest completed work and focuses on **new** reliability, UX, and maintainability opportunities for `devr`.


## 0.1.0 release additions to prioritize

1. **Add `python -m devr` module entrypoint support (done in this branch).**
   - This gives users a reliable fallback invocation path and improves post-install smoke testing.

2. **Run package artifact smoke tests as part of release steps.**
   - Build the wheel/sdist and verify the installed artifact can execute `devr --version` and `python -m devr --version`.

3. **Reconcile changelog and version state before tagging.**
   - `pyproject.toml` already says `0.1.0`, while `CHANGELOG.md` still has unreleased entries that read as already-shipped features.
   - Move completed items into the final `0.1.0` section (or bump target version if intentionally post-0.1.0 work).

## High-impact improvements

1. **Add machine-readable output modes (`--json`) for `check`, `security`, and `doctor`.**
   - Current output is human-friendly but hard to consume in CI dashboards and editor integrations.
   - A structured schema (status per stage, failing command, exit code, timings) would make automation significantly easier.

2. **Introduce a tool availability preflight before running stages.**
   - `check`/`security` assume required modules are installed in the selected venv.
   - A quick verification pass (e.g., `python -m <tool> --version`) with clear remediation hints would improve first-run UX and reduce confusing failures.

3. **Add timeout and cancellation controls for long-running commands.**
   - `git` calls currently have a timeout, but lint/type/test/security stages do not.
   - Command-level timeout settings (global + per-stage override) would protect CI jobs from hanging and improve reliability.

## Medium-impact improvements

4. **Support stage-level selection in `devr check`.**
   - Add options such as `--only lint,type,test` or `--skip type`.
   - This would improve developer workflow flexibility while keeping `devr` as a single entry point.

5. **Expand `--changed` support to compare against a configurable base ref.**
   - Today changed-file discovery is tied to local working tree/index state.
   - A mode like `--since origin/main` would better match PR workflows and reduce unnecessary checks in CI.

6. **Make security scan scope configurable.**
   - `bandit` currently scans recursively from project root with a fixed exclusion set.
   - Exposing include/exclude paths via config would allow teams to avoid vendored/generated directories and speed up scans.

## Nice-to-have improvements

7. **Add a dedicated `devr bootstrap` or `devr install-tools` command.**
   - `init` currently bundles environment creation, tool installation, project install, and pre-commit setup.
   - Splitting tool installation into an explicit command can make incremental adoption easier.

8. **Provide richer diagnostics in `doctor` (with optional checks mode).**
   - Potential additions: verify each tool importability, show Python/package versions, and surface config parse warnings.
   - An optional `doctor --check` mode could return non-zero status when critical setup issues are detected.

9. **Document cross-platform behavior and known constraints in a troubleshooting section.**
   - Add explicit notes on Windows path handling, active-venv precedence, git-required features, and typical failure recovery steps.

## Strengths observed

- The CLI command boundaries are clean and easy to follow.
- Configuration parsing remains defensive and pragmatic.
- Test coverage is broad across command behavior, failure paths, and edge-case handling.
