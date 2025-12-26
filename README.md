# pytest-uuid

A pytest plugin for mocking `uuid.uuid4()` calls in your tests.

[![PyPI version](https://img.shields.io/pypi/v/pytest-uuid.svg)](https://pypi.org/project/pytest-uuid/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/jason/pytest-uuid/actions/workflows/ci.yml/badge.svg)](https://github.com/jason/pytest-uuid/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![pytest](https://img.shields.io/badge/pytest-plugin-blue.svg)](https://docs.pytest.org/)

![Python 3.9](https://img.shields.io/badge/python-3.9-blue.svg)
![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)

## Installation

```bash
pip install pytest-uuid
```

## Usage

### Basic Usage

The plugin provides a `mock_uuid` fixture that automatically patches `uuid.uuid4()`:

```python
import uuid

def test_single_uuid(mock_uuid):
    # Set a specific UUID to return
    mock_uuid.set("12345678-1234-5678-1234-567812345678")

    result = uuid.uuid4()

    assert str(result) == "12345678-1234-5678-1234-567812345678"
```

### Multiple UUIDs

You can set multiple UUIDs that will be returned in sequence:

```python
import uuid

def test_multiple_uuids(mock_uuid):
    mock_uuid.set(
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
    )

    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
    assert str(uuid.uuid4()) == "33333333-3333-3333-3333-333333333333"
    # Cycles back to the first UUID
    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
```

### Default UUID

Set a default UUID that will be returned for all calls:

```python
import uuid

def test_default_uuid(mock_uuid):
    mock_uuid.set_default("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    # All calls return the same UUID
    assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
```

### Module-Specific Mocking

If your code imports `uuid4` directly (e.g., `from uuid import uuid4`), use the `mock_uuid_factory` fixture:

```python
# myapp/models.py
from uuid import uuid4

def create_user():
    return {"id": str(uuid4()), "name": "John"}

# tests/test_models.py
def test_create_user(mock_uuid_factory):
    with mock_uuid_factory("myapp.models") as mocker:
        mocker.set("12345678-1234-5678-1234-567812345678")

        user = create_user()

        assert user["id"] == "12345678-1234-5678-1234-567812345678"
```

### Reset

Reset the mocker to its initial state:

```python
def test_with_reset(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")

    # ... do something ...

    mock_uuid.reset()
    # Now uuid.uuid4() returns random UUIDs again
```

## API Reference

### `mock_uuid` fixture

A fixture that patches `uuid.uuid4` globally.

**Methods:**

- `set(*uuids)` - Set one or more UUIDs to return (cycles through if multiple)
- `set_default(uuid)` - Set a default UUID for all calls
- `reset()` - Reset to initial state (returns random UUIDs)

### `mock_uuid_factory` fixture

A fixture factory for mocking `uuid.uuid4()` in specific modules.

**Usage:**

```python
with mock_uuid_factory("module.path") as mocker:
    mocker.set("...")
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for package management and [just](https://just.systems/) as a command runner.

### Prerequisites

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (macOS)
brew install just

# Install just (other platforms)
# See: https://just.systems/man/en/installation.html
```

### Setup

```bash
# Clone the repository
git clone https://github.com/jason/pytest-uuid.git
cd pytest-uuid

# Sync dependencies (creates venv and installs deps)
just sync

# Or install in development mode
just install
```

### Available Commands

```bash
# List all available commands
just

# Run tests
just test

# Run tests with verbose output
just test-verbose

# Run tests across all Python versions
just test-all

# Run tests for a specific Python version
just test-py 3.12

# Run linting
just lint

# Format code
just format

# Run all checks
just check

# Build the package
just build

# Clean build artifacts
just clean
```

### Running Tests

```bash
# Run tests
just test

# Run with pytest options
just test -v --tb=short

# Run tests across all Python versions with nox
just test-all
```

### Linting and Formatting

```bash
# Check linting
just lint

# Check formatting
just format-check

# Format code (auto-fix)
just format
```

## License

MIT License - see [LICENSE](LICENSE) for details.
