"""Nox configuration for testing across Python versions."""

import nox

# Use uv as the package installer
nox.options.default_venv_backend = "uv"

PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13"]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the test suite."""
    session.install(".", "pytest")
    session.run("pytest", *session.posargs)


@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    """Run linting with ruff."""
    session.install("ruff")
    session.run("ruff", "check", "src", "tests", "noxfile.py")
    session.run("ruff", "format", "--check", "src", "tests", "noxfile.py")


@nox.session(python="3.12")
def format(session: nox.Session) -> None:
    """Format code with ruff."""
    session.install("ruff")
    session.run("ruff", "check", "--fix", "src", "tests", "noxfile.py")
    session.run("ruff", "format", "src", "tests", "noxfile.py")
