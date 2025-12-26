<img src="docs/images/logo.svg" alt="pytest-uuid logo" width="300" align="right" style="margin-top: -40px; margin-right: 20px;">

# pytest-uuid

A pytest plugin for mocking `uuid.uuid4()` calls in your tests.

[![PyPI version](https://img.shields.io/pypi/v/pytest-uuid.svg)](https://pypi.org/project/pytest-uuid/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/CaptainDriftwood/pytest-uuid/actions/workflows/test.yml/badge.svg)](https://github.com/CaptainDriftwood/pytest-uuid/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/CaptainDriftwood/pytest-uuid/graph/badge.svg)](https://codecov.io/gh/CaptainDriftwood/pytest-uuid)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![pytest](https://img.shields.io/badge/pytest-plugin-blue.svg)](https://docs.pytest.org/)

![Python](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue.svg)

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Development](#development)
- [License](#license)

## Features

- Mock `uuid.uuid4()` with deterministic values in your tests
- Works with both `import uuid` and `from uuid import uuid4` patterns
- Multiple ways to mock: static, sequence, seeded, or node-seeded
- Decorator, marker, and fixture APIs (inspired by freezegun)
- Configurable exhaustion behavior for sequences
- Ignore list for packages that should use real UUIDs
- Automatic cleanup after each test
- Zero configuration required - just use the fixture

## Installation

```bash
pip install pytest-uuid

# or with uv
uv add pytest-uuid
```

## Quick Start

### Fixture API

```python
import uuid

def test_single_uuid(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

def test_multiple_uuids(mock_uuid):
    mock_uuid.set(
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )
    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
    # Cycles back to the first UUID
    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
```

### Decorator API

```python
import uuid
from pytest_uuid import freeze_uuid

@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_with_decorator():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

@freeze_uuid(seed=42)
def test_seeded():
    # Reproducible UUIDs from seed
    result = uuid.uuid4()
    assert result.version == 4
```

### Marker API

```python
import uuid
import pytest

@pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_with_marker():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded():
    # Same test always gets the same UUIDs
    result = uuid.uuid4()
    assert result.version == 4
```

## Usage

### Static UUIDs

Return the same UUID every time:

```python
def test_static(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    assert uuid.uuid4() == uuid.uuid4()  # Same UUID

# Or with decorator
@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_static_decorator():
    assert uuid.uuid4() == uuid.uuid4()  # Same UUID
```

### UUID Sequences

Return UUIDs from a list:

```python
def test_sequence(mock_uuid):
    mock_uuid.set(
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    )
    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
    # Cycles back by default
    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
```

### Seeded UUIDs

Generate reproducible UUIDs from a seed:

```python
def test_seeded(mock_uuid):
    mock_uuid.set_seed(42)
    first = uuid.uuid4()

    mock_uuid.set_seed(42)  # Reset to same seed
    assert uuid.uuid4() == first  # Same UUID

# With decorator
@freeze_uuid(seed=42)
def test_seeded_decorator():
    result = uuid.uuid4()
    assert result.version == 4  # Valid UUID v4
```

### Node-Seeded UUIDs

Derive the seed from the test's node ID for automatic reproducibility:

```python
def test_node_seeded(mock_uuid):
    mock_uuid.set_seed_from_node()
    # Same test always produces the same sequence

# With marker
@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded_marker():
    # Same test always produces the same sequence
    pass
```

### Exhaustion Behavior

Control what happens when a UUID sequence is exhausted:

```python
from pytest_uuid import ExhaustionBehavior, UUIDsExhaustedError

def test_exhaustion_raise(mock_uuid):
    mock_uuid.set_exhaustion_behavior("raise")
    mock_uuid.set("11111111-1111-1111-1111-111111111111")

    uuid.uuid4()  # Returns the UUID

    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()  # Raises - sequence exhausted

# With decorator
@freeze_uuid(
    ["11111111-1111-1111-1111-111111111111"],
    on_exhausted="raise",  # or "cycle" or "random"
)
def test_exhaustion_decorator():
    uuid.uuid4()
    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()
```

Exhaustion behaviors:
- `"cycle"` (default): Loop back to the start of the sequence
- `"random"`: Fall back to generating random UUIDs
- `"raise"`: Raise `UUIDsExhaustedError`

### Global Configuration

Configure default behavior for all tests:

```python
# conftest.py
import pytest_uuid

pytest_uuid.configure(
    default_ignore_list=["sqlalchemy", "celery"],
    extend_ignore_list=["myapp.internal"],
    default_exhaustion_behavior="raise",
)
```

### Module-Specific Mocking

For granular control, use `mock_uuid_factory`:

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

### Context Manager

Use `freeze_uuid` as a context manager:

```python
from pytest_uuid import freeze_uuid

def test_context_manager():
    with freeze_uuid("12345678-1234-5678-1234-567812345678"):
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    # Original uuid.uuid4 is restored
    assert uuid.uuid4() != uuid.UUID("12345678-1234-5678-1234-567812345678")
```

### Bring Your Own Randomizer

Pass a `random.Random` instance for full control:

```python
import random
from pytest_uuid import freeze_uuid

rng = random.Random(42)
rng.random()  # Advance the state

@freeze_uuid(seed=rng)
def test_custom_rng():
    # Gets UUIDs from the pre-advanced random state
    result = uuid.uuid4()
```

### Scoped Mocking

#### Module-Level

Apply to all tests in a module using pytest's `pytestmark`:

```python
# tests/test_user_creation.py
import uuid
import pytest

pytestmark = pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")


def test_create_user():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"


def test_create_another_user():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

#### Class-Level

Apply the decorator to a test class to freeze UUIDs for all test methods:

```python
import uuid
from pytest_uuid import freeze_uuid


@freeze_uuid("12345678-1234-5678-1234-567812345678")
class TestUserService:
    def test_create(self):
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    def test_update(self):
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

Or use the marker:

```python
import uuid
import pytest


@pytest.mark.freeze_uuid(seed=42)
class TestSeededService:
    def test_one(self):
        result = uuid.uuid4()
        assert result.version == 4

    def test_two(self):
        result = uuid.uuid4()
        assert result.version == 4
```

#### Session-Level

For session-wide mocking, use a session-scoped autouse fixture in `conftest.py`:

```python
# conftest.py
import pytest
from pytest_uuid import freeze_uuid


@pytest.fixture(scope="session", autouse=True)
def freeze_uuids_globally():
    with freeze_uuid(seed=12345):
        yield
```

## API Reference

### Fixtures

#### `mock_uuid`

Main fixture for controlling `uuid.uuid4()` calls.

**Methods:**
- `set(*uuids)` - Set one or more UUIDs to return (cycles by default)
- `set_default(uuid)` - Set a default UUID for all calls
- `set_seed(seed)` - Set a seed for reproducible generation
- `set_seed_from_node()` - Use test node ID as seed
- `set_exhaustion_behavior(behavior)` - Set behavior when sequence exhausted
- `reset()` - Reset to initial state

#### `uuid_freezer`

Alias for `mock_uuid` following the freezegun naming pattern.

#### `mock_uuid_factory`

Factory for module-specific mocking.

```python
with mock_uuid_factory("module.path") as mocker:
    mocker.set("...")
```

### Decorator/Context Manager

#### `freeze_uuid`

```python
from pytest_uuid import freeze_uuid

# Static UUID
@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_static(): ...

# Sequence
@freeze_uuid(["uuid1", "uuid2"], on_exhausted="raise")
def test_sequence(): ...

# Seeded
@freeze_uuid(seed=42)
def test_seeded(): ...

# Node-seeded (for use with marker)
@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded(): ...

# Context manager
with freeze_uuid("...") as freezer:
    result = uuid.uuid4()
    freezer.reset()
```

**Parameters:**
- `uuids` - UUID(s) to return (string, UUID, or sequence)
- `seed` - Integer, `random.Random`, or `"node"` for reproducible generation
- `on_exhausted` - `"cycle"`, `"random"`, or `"raise"`
- `ignore` - Module prefixes to exclude from patching

### Marker

```python
@pytest.mark.freeze_uuid("uuid")
@pytest.mark.freeze_uuid(["uuid1", "uuid2"])
@pytest.mark.freeze_uuid(seed=42)
@pytest.mark.freeze_uuid(seed="node")
@pytest.mark.freeze_uuid("uuid", on_exhausted="raise")
```

### Configuration

```python
import pytest_uuid

pytest_uuid.configure(
    default_ignore_list=["package1", "package2"],
    extend_ignore_list=["package3"],
    default_exhaustion_behavior="raise",
)
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for package management and [just](https://just.systems/) as a command runner.

### Prerequisites

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (macOS)
brew install just
```

### Setup

```bash
git clone https://github.com/CaptainDriftwood/pytest-uuid.git
cd pytest-uuid
just sync
```

### Available Commands

```bash
just              # List all commands
just test         # Run tests
just test-cov     # Run tests with coverage
just nox          # Run tests across all Python versions with nox
just nox 3.12     # Run tests for a specific Python version
just lint         # Run linting
just format       # Format code
just check        # Run all checks
just build        # Build the package
```

### Coverage with Pytester

This project uses [pytester](https://docs.pytest.org/en/stable/reference/reference.html#pytester) for integration testing. Getting accurate coverage for pytest plugins requires special handling because plugins are imported before coverage can start measuring.

**The Problem:**

When running `pytest --cov=pytest_uuid`, the plugin is loaded when pytest starts—*before* pytest-cov begins measuring. This causes incomplete coverage and the warning:

```
CoverageWarning: Module pytest_uuid was previously imported, but not measured
```

**The Solution:**

Use `coverage run -m pytest` instead of `pytest --cov`:

```bash
# Instead of this:
pytest --cov=pytest_uuid --cov-report=term-missing

# Use this:
coverage run -m pytest
coverage combine
coverage report --show-missing
```

This works because `coverage run` starts measuring *before* Python imports anything, so the plugin import is captured.

**Configuration (`pyproject.toml`):**

```toml
[tool.coverage.run]
source = ["src/pytest_uuid"]
branch = true
parallel = true           # Required for combining coverage files
patch = ["subprocess"]    # Enables coverage in subprocesses
sigterm = true            # Ensures coverage is saved on SIGTERM
```

**Why `parallel = true`?**

When coverage patches subprocesses, each subprocess writes its own `.coverage.<hostname>.<pid>.<random>` file. The `coverage combine` command merges these into a single `.coverage` file for reporting.

**References:**

- [pytest-cov Subprocess Support](https://pytest-cov.readthedocs.io/en/latest/subprocess-support.html)
- [coverage.py Subprocess Measurement](https://coverage.readthedocs.io/en/latest/subprocess.html)
- [pytest-cov Issue #587 - Plugin Coverage](https://github.com/pytest-dev/pytest-cov/issues/587)

## License

MIT License - see [LICENSE](LICENSE) for details.
