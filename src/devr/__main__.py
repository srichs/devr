"""Module entry point for ``python -m devr``."""

from .cli import app


if __name__ == "__main__":
    app(prog_name="devr")
