# devr

**devr** runs your Python dev “preflight” — lint, formatting, type checking, tests, and coverage — **inside your project’s virtualenv**.

It’s designed to be easy for developers:
- One install (recommended via `pipx`)
- One command to set up a repo: `devr init`
- One command to gate changes: `devr check`
- Optional pre-commit hook that runs the same gate on staged files

## Why devr?

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

Recommended:

```bash
pipx install devr
