# Marker API

The `@pytest.mark.freeze_uuid` marker integrates with pytest's marker system for declarative UUID mocking.

## Basic Usage

```python
import uuid
import pytest

@pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
def test_with_marker():
    assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
```

## Multiple UUIDs

```python
@pytest.mark.freeze_uuid([
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
])
def test_sequence():
    assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
```

## Seeded UUIDs

```python
@pytest.mark.freeze_uuid(seed=42)
def test_seeded():
    result = uuid.uuid4()
    assert result.version == 4
```

## Node-Seeded UUIDs (Recommended)

The `seed="node"` option derives the seed from the test's fully-qualified name:

```python
@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded():
    # This test always produces the same UUIDs
    # Different tests get different sequences
    result = uuid.uuid4()
    assert result.version == 4
```

!!! tip "Why node seeding is recommended"
    Node-seeded UUIDs give you deterministic, reproducible tests without the maintenance burden of hardcoded UUIDs. Each test gets its own unique seed derived from its fully-qualified name (e.g., `test_module.py::TestClass::test_method`), so tests are isolated and don't affect each other.

## Class-Level Marker

Apply to all methods in a test class:

```python
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

## Module-Level Marker

Apply to all tests in a module using `pytestmark`:

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

## Exhaustion Behavior

```python
import uuid
import pytest
from pytest_uuid import UUIDsExhaustedError

@pytest.mark.freeze_uuid(
    "11111111-1111-4111-8111-111111111111",
    on_exhausted="raise",
)
def test_exhaustion():
    uuid.uuid4()  # OK
    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()  # Raises
```

## Ignoring Modules

```python
@pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678", ignore=["celery"])
def test_with_ignored():
    pass
```

## Opting Out of Default Ignores

By default, packages like `botocore` are always ignored. Use `ignore_defaults=False` to mock them:

```python
@pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678", ignore_defaults=False)
def test_mock_everything():
    # All uuid.uuid4() calls are mocked, including from botocore
    pass
```

## Session-Level Configuration

For session-wide mocking, use a session-scoped autouse fixture in `conftest.py`:

```python
# conftest.py
import hashlib

import pytest
from pytest_uuid import freeze_uuid


@pytest.fixture(scope="session", autouse=True)
def freeze_uuids_globally(request):
    # Use hashlib for deterministic seeding across processes.
    # Python's hash() is randomized per-process via PYTHONHASHSEED:
    # https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED
    #
    # Convert node ID to a deterministic integer seed:
    # 1. hashlib.sha256() creates a hash of the node ID string
    # 2. .hexdigest() returns the hash as a 64-char hex string
    # 3. [:16] takes first 16 hex chars (64 bits) - plenty of uniqueness
    # 4. int(..., 16) converts hex string to integer
    node_bytes = request.node.nodeid.encode()
    seed = int(hashlib.sha256(node_bytes).hexdigest()[:16], 16)
    with freeze_uuid(seed=seed):
        yield
```

!!! note
    For session-level fixtures, use `request.node.nodeid` directly since `seed="node"` in the marker requires per-test context. Always use `hashlib` (not `hash()`) for node-derived seeds, as Python's built-in `hash()` is randomized per-process.

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `uuids` | `str`, `UUID`, or sequence | UUID(s) to return |
| `seed` | `int` or `"node"` | Seed for reproducible generation |
| `on_exhausted` | `str` | `"cycle"`, `"random"`, or `"raise"` |
| `ignore` | `list[str]` | Module prefixes to exclude from mocking |
| `ignore_defaults` | `bool` | Include default ignore list (default `True`) |