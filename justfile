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
    just test -v

# Run tests with coverage
test-cov:
    uv run coverage run -m pytest
    uv run coverage combine
    uv run coverage report --show-missing

# Run tests with coverage and open HTML report
test-cov-html:
    uv run coverage run -m pytest
    uv run coverage combine
    uv run coverage html
    open htmlcov/index.html

# Run tests in random order using pytest-randomly
test-randomly *args:
    uv run --with pytest-randomly pytest {{ args }}

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

# Run type checking
type:
    uv run ty check src/

# Run formatter check
format-check:
    uv run ruff format --check src tests noxfile.py

# Format code and sort imports (isort convention)
format:
    uv run ruff check --select I --fix src tests noxfile.py
    uv run ruff format src tests noxfile.py

# Alias for format
fmt: format

# Run all code quality checks (format + lint + type + test)
check:
    just format-check
    just lint
    just type
    just test

# Show what ignored files would be cleaned (dry run)
clean-dry-run:
    git clean -Xdn | grep -v -E '\.venv|\.idea|\.claude|CLAUDE\.md' || true

# Clean ignored files (excluding .venv, .idea, .claude, CLAUDE.md)
clean:
    #!/usr/bin/env bash
    git clean -Xdn | grep -v -E '\.venv|\.idea|\.claude|CLAUDE\.md' | sed 's/Would remove //' | while read -r f; do [ -n "$f" ] && rm -rf "$f"; done

# Show what untracked files would be cleaned (dry run)
clean-untracked-dry-run:
    git clean -dn -e .venv -e .idea -e .claude -e CLAUDE.md

# Clean only untracked files (excluding .venv, .idea, .claude, CLAUDE.md)
clean-untracked:
    git clean -df -e .venv -e .idea -e .claude -e CLAUDE.md

# Show what all files would be cleaned (dry run)
clean-all-dry-run:
    git clean -xdn -e .venv -e .idea -e .claude -e CLAUDE.md

# Clean all files: ignored + untracked (excluding .venv, .idea, .claude, CLAUDE.md)
clean-all:
    git clean -xdf -e .venv -e .idea -e .claude -e CLAUDE.md

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
