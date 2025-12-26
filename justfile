# Default recipe - show available commands
default:
    @just --list

# Install the package in development mode
install:
    uv pip install -e ".[dev]"

# Install just the package (no dev dependencies)
install-prod:
    uv pip install -e .

# Run tests
test *args:
    uv run pytest {{ args }}

# Run tests with verbose output
test-verbose:
    uv run pytest -v

# Run tests with coverage
test-cov:
    uv run pytest --cov=pytest_uuid --cov-report=term-missing

# Run tests with nox (optionally specify Python version, e.g., just nox 3.12)
nox version="":
    #!/usr/bin/env bash
    if [ -z "{{ version }}" ]; then
        uvx --with nox-uv nox -s tests
    else
        uvx --with nox-uv nox -s tests-{{ version }}
    fi

# Run linting
lint:
    uv run ruff check src tests noxfile.py

# Run formatter check
format-check:
    uv run ruff format --check src tests noxfile.py

# Format code and sort imports (isort convention)
format:
    uv run ruff check --select I --fix src tests noxfile.py
    uv run ruff format src tests noxfile.py

# Run all code quality checks (lint + import sorting + format)
check:
    uv run ruff check src tests noxfile.py
    uv run ruff format --check src tests noxfile.py

# Clean build artifacts
clean:
    rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache .nox .coverage htmlcov
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete

# Build the package
build: clean
    uv build

# Sync dependencies (create/update venv)
sync:
    uv sync

# Lock dependencies
lock:
    uv lock

# Publish to PyPI (requires TWINE_USERNAME and TWINE_PASSWORD or .pypirc)
publish: build
    uv run twine upload dist/*

# Publish to TestPyPI
publish-test: build
    uv run twine upload --repository testpypi dist/*
