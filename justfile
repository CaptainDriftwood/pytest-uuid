# Default recipe - show available commands
default:
    @just --list

# Install the package in development mode
install:
    uv pip install -e ".[dev]"

# Install just the package (no dev dependencies)
install-prod:
    uv pip install -e .

# Run tests (excludes slow tests for fast iteration)
test *args:
    uv run pytest tests/ -p no:randomly -n auto --dist loadscope -m "not slow" {{ args }}

# Run all tests including slow ones
test-all *args:
    uv run pytest tests/ -p no:randomly -n auto --dist loadscope {{ args }}

# Run only slow tests
test-slow *args:
    uv run pytest tests/ -p no:randomly -n auto --dist loadscope -m "slow" {{ args }}

# Run tests with verbose output
test-verbose:
    just test -v

# Run tests with coverage (deterministic order)
test-cov:
    uv run coverage run -m pytest -p no:randomly
    uv run coverage combine
    uv run coverage report --show-missing

# Run tests with coverage and open HTML report (deterministic order)
test-cov-html:
    uv run coverage run -m pytest -p no:randomly
    uv run coverage combine
    uv run coverage html
    open htmlcov/index.html

# Run tests in random order using pytest-randomly
test-randomly *args:
    uv run pytest {{ args }}

# Run stress tests for parallel execution (catches race conditions)
test-stress *args:
    uv run pytest tests/integration/test_stress_parallel.py -n auto --dist loadscope -v {{ args }}

# Run aggressive parallel stress tests (multiple pytest processes via Make -j)
# Usage: just test-stress-parallel 4  (runs 4 parallel pytest processes)
test-stress-parallel jobs="4":
    make -j{{ jobs }} stress-test XDIST_WORKERS=2

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

# Sync dependencies (create/update venv with all groups)
sync:
    uv sync --all-groups

# Lock dependencies
lock:
    uv lock

# Publish to PyPI (requires TWINE_USERNAME and TWINE_PASSWORD or .pypirc)
publish: build
    uv run twine upload dist/*

# Publish to TestPyPI
publish-test: build
    uv run twine upload --repository testpypi dist/*

# Serve documentation locally
docs:
    uv sync --group docs
    uv run mkdocs serve

# Build documentation
docs-build:
    uv sync --group docs
    uv run mkdocs build --strict
