Usage guide
===========

This guide explains how to use ``devr`` day-to-day, from first-time setup to
common CI and local workflows.

What ``devr`` does
------------------

``devr`` runs your development quality gate inside your project virtual
environment:

- Linting
- Formatting checks (or formatting fixes)
- Type checking
- Test execution with coverage threshold
- Optional security checks via ``devr security``

The main goal is consistency: run one command locally and in CI, and use the
same tools and interpreter.

Install
-------

You can install globally with ``pipx`` (recommended):

.. code-block:: bash

   pipx install devr

Or install with ``pip``:

.. code-block:: bash

   pip install devr

Typical project setup
---------------------

From a project root, run:

.. code-block:: bash

   devr init

``devr init`` performs the following steps:

1. Find an existing virtual environment, or create one.
2. Install and upgrade core packaging tools in the venv.
3. Install the default dev toolchain (ruff, black, mypy, pyright, pytest,
   pytest-cov, pre-commit, pip-audit, bandit).
4. Install your project dependencies:

   - ``pip install -e .`` when ``pyproject.toml`` exists.
   - fallback to ``pip install .`` if editable install fails.
   - or ``pip install -r requirements.txt`` when present.

5. Create ``.pre-commit-config.yaml`` if missing.
6. Install the git pre-commit hook.

If no git repository is present, pre-commit hook installation is skipped.

Run the full check
------------------

Use this command before commits and pull requests:

.. code-block:: bash

   devr check

By default this runs:

1. Lint + formatting check
2. Type checking
3. Tests with coverage threshold

If all stages pass, ``devr`` exits successfully.

Using ``--fix``
---------------

To apply safe autofixes:

.. code-block:: bash

   devr check --fix

With ``--fix``:

- Ruff fixes lint issues that are safe to auto-correct.
- Formatter is applied directly.

You can also use:

.. code-block:: bash

   devr fix

``devr fix`` runs the fixer/formatter stages only.

Changed-files workflows
-----------------------

When you want faster feedback on only touched files:

.. code-block:: bash

   devr check --changed

For pre-commit-friendly behavior, combine staged and changed:

.. code-block:: bash

   devr check --staged --changed

Notes:

- ``--staged`` has effect only when ``--changed`` is also set.
- Changed mode scopes lint/format and type checking targets to changed Python
  files.
- If no Python files are selected, lint/format and type-checking stages are
  skipped gracefully.

Skipping tests intentionally
----------------------------

For quicker checks:

.. code-block:: bash

   devr check --fast

To always skip tests for the current command:

.. code-block:: bash

   devr check --no-tests

Difference:

- ``--fast`` is a convenience mode for faster feedback.
- ``--no-tests`` is explicit and always skips tests regardless of configuration.

Security checks
---------------

Run dependency and static-analysis scans:

.. code-block:: bash

   devr security

This runs:

- ``pip-audit`` for dependency vulnerabilities
- ``bandit`` for code-level security analysis

If either tool fails, ``devr security`` exits non-zero.

Configuration in ``pyproject.toml``
-----------------------------------

Configure ``devr`` under ``[tool.devr]``:

.. code-block:: toml

   [tool.devr]
   venv_path = ".venv"
   formatter = "ruff"      # or "black"
   typechecker = "mypy"    # or "pyright"
   coverage_min = 85
   coverage_branch = true
   run_tests = true

Configuration behavior:

- Invalid or missing values fall back to defaults.
- ``coverage_min`` is clamped by validation (0 to 100 accepted).
- ``formatter`` supports ``ruff`` and ``black``.
- ``typechecker`` supports ``mypy`` and ``pyright``.

Recommended local workflow
--------------------------

For most contributors:

1. ``devr init`` once per repo (or when tools/config changes).
2. Develop normally.
3. Run ``devr check --staged --changed`` for quick pre-commit checks.
4. Run ``devr check`` before opening a PR.
5. Optionally run ``devr security`` for security-focused changes.

Recommended CI workflow
-----------------------

In CI, run:

.. code-block:: bash

   devr check

Optionally add:

.. code-block:: bash

   devr security

This keeps your local and CI quality gates aligned.

Troubleshooting
---------------

No venv found
^^^^^^^^^^^^^

If ``devr check`` says no venv was found, run:

.. code-block:: bash

   devr init

Project install warning during init
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``devr init`` treats project installation as best-effort. If your package setup
is incomplete, toolchain setup still succeeds and you can resolve packaging
issues separately.

No changed files detected
^^^^^^^^^^^^^^^^^^^^^^^^^

In ``--changed`` mode, no matching Python files means relevant stages are
skipped. This is expected for docs-only or non-Python changes.

Git not available
^^^^^^^^^^^^^^^^^

Some changed/staged features rely on git metadata. Outside a git repository,
``devr`` may skip git-dependent behavior and continue with available stages.

Command reference (quick lookup)
--------------------------------

- ``devr init [--python python3.12]``
- ``devr check [--fix] [--staged --changed] [--fast] [--no-tests]``
- ``devr fix``
- ``devr security``
