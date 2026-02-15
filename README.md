# devr

**devr** runs your Python dev “preflight” — lint, formatting, type checking, tests, and coverage — **inside your project’s virtualenv**.

It’s designed to be easy for developers:
- One install (recommended via `pipx`)
- One command to set up a repo: `devr init`
- One command to gate changes: `devr check`
- Optional pre-commit hook that runs the same gate on staged files

---

## Install

Recommended:

```bash
pipx install devr
