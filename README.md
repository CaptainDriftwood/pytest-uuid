<p align="center">
  <img src="https://raw.githubusercontent.com/CaptainDriftwood/pytest-uuid/master/docs/images/logo.svg" alt="pytest-uuid logo" width="300">
</p>

<h1 align="center">pytest-uuid</h1>

A pytest plugin for mocking `uuid.uuid4()` calls in your tests.

[![PyPI version](https://img.shields.io/pypi/v/pytest-uuid.svg)](https://pypi.org/project/pytest-uuid/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/CaptainDriftwood/pytest-uuid/actions/workflows/test.yml/badge.svg)](https://github.com/CaptainDriftwood/pytest-uuid/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/CaptainDriftwood/pytest-uuid/graph/badge.svg)](https://codecov.io/gh/CaptainDriftwood/pytest-uuid)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
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
- Spy mode to track calls without mocking
- Detailed call tracking with caller module/file info
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

### Node-Seeded UUIDs (Recommended)

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

> **Why node seeding is recommended:** Node-seeded UUIDs give you deterministic, reproducible tests without the maintenance burden of hardcoded UUIDs. Each test gets its own unique seed derived from its fully-qualified name (e.g., `test_module.py::TestClass::test_method`), so tests are isolated and don't affect each other. When a test fails, you get the same UUIDs on every run, making debugging easier. Unlike static UUIDs, you never have to update test files when adding new UUID calls.

#### Class-Level Node Seeding

```python
import uuid
import pytest


@pytest.mark.freeze_uuid(seed="node")
class TestUserService:
    def test_create(self):
        # Seed derived from "test_module.py::TestUserService::test_create"
        result = uuid.uuid4()
        assert result.version == 4

    def test_update(self):
        # Seed derived from "test_module.py::TestUserService::test_update"
        result = uuid.uuid4()
        assert result.version == 4
```

#### Module-Level Node Seeding

```python
# tests/test_user_creation.py
import uuid
import pytest

pytestmark = pytest.mark.freeze_uuid(seed="node")


def test_create_user():
    # Seed derived from "test_user_creation.py::test_create_user"
    result = uuid.uuid4()
    assert result.version == 4


def test_create_admin():
    # Seed derived from "test_user_creation.py::test_create_admin"
    result = uuid.uuid4()
    assert result.version == 4
```

#### Session-Level Node Seeding

```python
# conftest.py
import pytest
from pytest_uuid import freeze_uuid


@pytest.fixture(scope="session", autouse=True)
def freeze_uuids_globally(request):
    # Use session node ID as seed for all tests
    seed = hash(request.node.nodeid)
    with freeze_uuid(seed=seed):
        yield
```

> **Note:** For session-level fixtures, use `request.node.nodeid` directly since `seed="node"` in the marker requires per-test context. Alternatively, use a fixed seed for true global determinism.

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

### Spy Mode

Track `uuid.uuid4()` calls without mocking them. Useful when you need to verify UUID generation happens without controlling the output.

#### Using `spy_uuid` Fixture

```python
# myapp/models.py
from uuid import uuid4

class User:
    def __init__(self, name):
        self.id = str(uuid4())
        self.name = name

# tests/test_models.py
def test_user_generates_uuid(spy_uuid):
    """Verify User creates a UUID without controlling its value."""
    user = User("Alice")

    assert spy_uuid.call_count == 1
    assert user.id == str(spy_uuid.last_uuid)
```

#### Using `mock_uuid.spy()`

Switch from mocked to real UUIDs mid-test:

```python
def test_start_mocked_then_spy(mock_uuid):
    """Start with mocked UUIDs, then switch to real ones."""
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    first = uuid.uuid4()  # Mocked

    mock_uuid.spy()  # Switch to spy mode
    second = uuid.uuid4()  # Real random UUID

    assert str(first) == "12345678-1234-5678-1234-567812345678"
    assert first != second  # second is random
    assert mock_uuid.mocked_count == 1
    assert mock_uuid.real_count == 1
```

> **When to use which:** Use `spy_uuid` when you never need mocking in the test. Use `mock_uuid.spy()` when you need to switch between mocked and real UUIDs within the same test.

### Ignoring Modules

Exclude specific packages from UUID mocking so they receive real UUIDs. This is useful for third-party libraries like SQLAlchemy or Celery that need real UUIDs for internal operations.

#### Fixture API

```python
def test_with_ignored_modules(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    mock_uuid.set_ignore("sqlalchemy", "celery")

    # Direct calls are mocked
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    # Calls from sqlalchemy/celery get real UUIDs
    # (the ignore check walks the entire call stack)
```

#### Decorator/Marker API

```python
@freeze_uuid("12345678-1234-5678-1234-567812345678", ignore=["sqlalchemy"])
def test_with_decorator():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

@pytest.mark.freeze_uuid("...", ignore=["celery"])
def test_with_marker():
    pass
```

> **How it works:** The ignore check inspects the entire call stack, not just the immediate caller. If any frame in the call chain is from an ignored module, real UUIDs are returned. This handles cases where your code calls a library that internally calls `uuid.uuid4()`.

#### Tracking Ignored Calls

```python
def test_tracking(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    mock_uuid.set_ignore("mylib")

    uuid.uuid4()           # mocked
    mylib.create_record()  # real (from ignored module)

    assert mock_uuid.mocked_count == 1
    assert mock_uuid.real_count == 1
```

### Global Configuration

Configure default behavior for all tests via `pyproject.toml`:

```toml
# pyproject.toml
[tool.pytest_uuid]
default_ignore_list = ["sqlalchemy", "celery"]
extend_ignore_list = ["myapp.internal"]
default_exhaustion_behavior = "raise"
```

Or programmatically in `conftest.py`:

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
- `spy()` - Switch to spy mode (return real UUIDs while still tracking)
- `reset()` - Reset to initial state
- `set_ignore(*module_prefixes)` - Set modules to ignore (returns real UUIDs)

#### `mock_uuid_factory`

Factory for module-specific mocking.

```python
with mock_uuid_factory("module.path") as mocker:
    mocker.set("...")
```

#### `spy_uuid`

Spy fixture that tracks `uuid.uuid4()` calls without mocking them.

```python
def test_spy(spy_uuid):
    result = uuid.uuid4()  # Returns real random UUID

    assert spy_uuid.call_count == 1
    assert spy_uuid.last_uuid == result
```

**Properties:**
- `call_count` - Number of times uuid4 was called
- `generated_uuids` - List of all generated UUIDs
- `last_uuid` - Most recently generated UUID
- `calls` - List of `UUIDCall` records with metadata

**Methods:**
- `reset()` - Reset tracking data
- `calls_from(module_prefix)` - Filter calls by module prefix

### Call Tracking

Both `mock_uuid` and `spy_uuid` fixtures provide detailed call tracking via the `UUIDCall` dataclass:

```python
from pytest_uuid.types import UUIDCall

def test_call_tracking(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    uuid.uuid4()

    call = mock_uuid.calls[0]
    assert call.uuid == uuid.UUID("12345678-1234-5678-1234-567812345678")
    assert call.was_mocked is True
    assert call.caller_module is not None
    assert call.caller_file is not None
```

**`UUIDCall` Fields:**
- `uuid` - The UUID that was returned
- `was_mocked` - `True` if mocked, `False` if real (spy mode or ignored module)
- `caller_module` - Name of the module that made the call
- `caller_file` - File path where the call originated

**Tracking Properties** (available on both `mock_uuid` and `spy_uuid`):
- `call_count` - Total number of uuid4 calls
- `generated_uuids` - List of all UUIDs returned
- `last_uuid` - Most recently returned UUID
- `calls` - List of `UUIDCall` records with full metadata

**Additional `mock_uuid` Properties:**
- `mocked_calls` - Only calls that returned mocked UUIDs
- `real_calls` - Only calls that returned real UUIDs (spy mode or ignored modules)
- `mocked_count` - Number of mocked calls
- `real_count` - Number of real calls

#### Interrogating Multiple Calls

```python
def test_interrogate_calls(mock_uuid):
    """Inspect detailed metadata for all uuid4 calls."""
    mock_uuid.set(
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    )

    first = uuid.uuid4()
    second = uuid.uuid4()

    # Check all UUIDs generated
    assert len(mock_uuid.generated_uuids) == 2
    assert mock_uuid.generated_uuids[0] == first
    assert mock_uuid.generated_uuids[1] == second

    # Get the last UUID quickly
    assert mock_uuid.last_uuid == second

    # Iterate through call details
    for i, call in enumerate(mock_uuid.calls):
        print(f"Call {i}: {call.uuid}")
        print(f"  Module: {call.caller_module}")
        print(f"  File: {call.caller_file}")
        print(f"  Mocked: {call.was_mocked}")
```

#### Distinguishing Mocked vs Real Calls

```python
def test_mixed_mocked_and_real(mock_uuid):
    """Track both mocked calls and real calls from ignored modules."""
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    mock_uuid.set_ignore("mylib")

    uuid.uuid4()              # Mocked (direct call)
    mylib.create_record()     # Real (from ignored module)
    uuid.uuid4()              # Mocked (direct call)

    # Count by type
    assert mock_uuid.call_count == 3
    assert mock_uuid.mocked_count == 2
    assert mock_uuid.real_count == 1

    # Access only real calls
    for call in mock_uuid.real_calls:
        print(f"Real UUID from {call.caller_module}: {call.uuid}")

    # Access only mocked calls
    for call in mock_uuid.mocked_calls:
        assert call.was_mocked is True
```

#### Filtering Calls by Module

```python
def test_filter_calls(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")

    uuid.uuid4()  # Call from test module
    mymodule.do_something()  # Calls uuid4 internally

    # Filter calls by module prefix
    test_calls = mock_uuid.calls_from("tests")
    module_calls = mock_uuid.calls_from("mymodule")

    # Useful for verifying specific modules made expected calls
    assert len(module_calls) == 1
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

### References

- [RFC 9562 - UUID Specification](https://datatracker.ietf.org/doc/html/rfc9562)

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
