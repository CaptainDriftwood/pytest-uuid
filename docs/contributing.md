# Contributing

Thank you for your interest in contributing to pytest-uuid!

## Development Setup

### Prerequisites

- Python 3.9 or higher
- [uv](https://docs.astral.sh/uv/) for package management
- [just](https://just.systems/) as a command runner

### Installation

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (macOS)
brew install just

# Clone and setup
git clone https://github.com/CaptainDriftwood/pytest-uuid.git
cd pytest-uuid
just sync
```

## Development Commands

```bash
just              # List all commands
just test         # Run fast tests (excludes slow pytest-venv tests)
just test-all     # Run all tests including slow ones
just test-slow    # Run only slow tests (pytest-venv integration tests)
just test-stress  # Run parallel execution stress tests
just test-cov     # Run tests with coverage
just nox          # Run tests across all Python versions
just nox 3.12     # Run tests for specific Python version
just lint         # Run linting
just format       # Format code
just check        # Run all checks
just build        # Build the package
```

## Code Style

- Follow the ruff configuration in `pyproject.toml`
- Line length: 88 characters
- Use double quotes for strings
- Run `just lint` before submitting

### Type Hints

- Use type hints consistent with `types.py` protocols
- Target Python 3.9+ compatibility
- Use `Union` instead of `|` for type unions

```python
# Good
from typing import Union, Optional
def example(value: Union[str, int]) -> Optional[str]:
    pass

# Avoid (Python 3.10+ only)
def example(value: str | int) -> str | None:
    pass
```

## Testing

- Run `just test` before submitting
- Add tests for new functionality
- Use pytester for integration tests that verify pytest plugin behavior
- Follow existing test file organization (`test_<module>.py` pattern)

### Running Tests

```bash
# Fast tests (recommended for development iteration)
just test

# All tests including slow pytest-venv integration tests
just test-all

# Only slow tests (pytest-venv tests that create real virtualenvs)
just test-slow

# Parallel execution stress tests
just test-stress

# With coverage
just test-cov

# Specific test file
pytest tests/test_fixtures.py

# Specific test
pytest tests/test_fixtures.py::test_mock_uuid_basic
```

!!! note "Test Speed"
    `just test` excludes tests marked with `@pytest.mark.slow` for fast feedback during development. These slow tests use pytest-venv to create real virtual environments and install packages, which takes ~45 seconds. Run `just test-all` before submitting a PR to ensure all tests pass.

### Coverage

```bash
# Run with coverage
coverage run -m pytest
coverage combine
coverage report --show-missing
```

## Architecture

### Key Patterns

- Generators inherit from `UUIDGenerator` base class
- New fixtures follow the protocol pattern in `types.py`
- Use `_find_uuid4_imports()` pattern for module discovery
- Prefer extending existing classes over creating new ones

### Common Pitfalls

- Always clean up patches in pytest hooks (`pytest_runtest_teardown`)
- Be careful with module import order when patching

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`just check`)
5. Commit your changes
6. Push to your fork
7. Open a Pull Request

### PR Guidelines

- Keep PRs focused on a single change
- Update documentation if needed
- Add tests for new functionality
- Follow the existing code style

## Issues

Found a bug or have a feature request? Please [open an issue](https://github.com/CaptainDriftwood/pytest-uuid/issues/new).

### Bug Reports

Include:

- Python version
- pytest version
- pytest-uuid version
- Minimal reproduction code
- Expected vs actual behavior

### Feature Requests

Include:

- Use case description
- Proposed API (if applicable)
- Any related issues or discussions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.