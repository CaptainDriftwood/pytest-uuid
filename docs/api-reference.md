# API Reference

Complete API documentation for pytest-uuid.

## Fixtures

### mock_uuid

Main fixture for controlling `uuid.uuid4()` calls.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `set` | `set(*uuids: str \| UUID)` | Set one or more UUIDs to return |
| `set_default` | `set_default(uuid: str \| UUID)` | Set a default UUID for all calls |
| `set_seed` | `set_seed(seed: int)` | Set a seed for reproducible generation |
| `set_seed_from_node` | `set_seed_from_node()` | Use test node ID as seed |
| `set_exhaustion_behavior` | `set_exhaustion_behavior(behavior: str)` | Set exhaustion behavior |
| `set_ignore` | `set_ignore(*module_prefixes: str)` | Set modules to ignore |
| `spy` | `spy()` | Switch to spy mode |
| `reset` | `reset()` | Reset to initial state |

**Tracking Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `call_count` | `int` | Total uuid4 calls |
| `generated_uuids` | `list[UUID]` | All returned UUIDs |
| `last_uuid` | `UUID \| None` | Most recent UUID |
| `calls` | `list[UUIDCall]` | Call records with metadata |
| `mocked_calls` | `list[UUIDCall]` | Only mocked calls |
| `real_calls` | `list[UUIDCall]` | Only real calls |
| `mocked_count` | `int` | Number of mocked calls |
| `real_count` | `int` | Number of real calls |

**Filtering Method:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `calls_from` | `calls_from(module_prefix: str) -> list[UUIDCall]` | Filter calls by module |

---

### mock_uuid_factory

Factory for module-specific mocking.

**Usage:**

```python
def test_example(mock_uuid_factory):
    with mock_uuid_factory("myapp.models") as mocker:
        mocker.set("12345678-1234-5678-1234-567812345678")
        # Only myapp.models.uuid4 is mocked
```

---

### spy_uuid

Spy fixture that tracks `uuid.uuid4()` calls without mocking.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `call_count` | `int` | Number of uuid4 calls |
| `generated_uuids` | `list[UUID]` | All generated UUIDs |
| `last_uuid` | `UUID \| None` | Most recent UUID |
| `calls` | `list[UUIDCall]` | Call records with metadata |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `reset` | `reset()` | Reset tracking data |
| `calls_from` | `calls_from(module_prefix: str) -> list[UUIDCall]` | Filter calls by module |

---

## Decorator / Context Manager

### freeze_uuid

```python
from pytest_uuid import freeze_uuid
```

**Signature:**

```python
freeze_uuid(
    uuids: str | UUID | Sequence[str | UUID] = None,
    *,
    seed: int | Random | Literal["node"] = None,
    on_exhausted: Literal["cycle", "random", "raise"] = "cycle",
    ignore: Sequence[str] = None,
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `uuids` | `str`, `UUID`, or sequence | `None` | UUID(s) to return |
| `seed` | `int`, `Random`, or `"node"` | `None` | Seed for reproducible generation |
| `on_exhausted` | `str` | `"cycle"` | Exhaustion behavior |
| `ignore` | `Sequence[str]` | `None` | Modules to exclude |

**Usage as decorator:**

```python
@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_example():
    pass
```

**Usage as context manager:**

```python
with freeze_uuid("12345678-1234-5678-1234-567812345678") as freezer:
    uuid.uuid4()
    freezer.reset()
```

---

## Marker

### @pytest.mark.freeze_uuid

```python
@pytest.mark.freeze_uuid(uuids, *, seed=None, on_exhausted="cycle", ignore=None)
```

**Parameters:**

Same as `freeze_uuid` decorator, except `seed` cannot be a `Random` instance (use `int` or `"node"`).

**Examples:**

```python
@pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_static(): ...

@pytest.mark.freeze_uuid(seed=42)
def test_seeded(): ...

@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded(): ...
```

---

## Types

### UUIDCall

Dataclass containing call metadata.

```python
from pytest_uuid.types import UUIDCall
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | `UUID` | The returned UUID |
| `was_mocked` | `bool` | Whether the UUID was mocked |
| `caller_module` | `str \| None` | Module that made the call |
| `caller_file` | `str \| None` | File path of the call |

---

### ExhaustionBehavior

Enum for exhaustion behavior.

```python
from pytest_uuid import ExhaustionBehavior

ExhaustionBehavior.CYCLE   # Loop back to start
ExhaustionBehavior.RANDOM  # Generate random UUIDs
ExhaustionBehavior.RAISE   # Raise UUIDsExhaustedError
```

---

## Exceptions

### UUIDsExhaustedError

Raised when UUID sequence is exhausted and behavior is `"raise"`.

```python
import uuid
import pytest
from pytest_uuid import UUIDsExhaustedError

with pytest.raises(UUIDsExhaustedError):
    uuid.uuid4()
```

---

## Configuration

### configure()

```python
import pytest_uuid

pytest_uuid.configure(
    default_ignore_list: Sequence[str] = None,
    extend_ignore_list: Sequence[str] = None,
    default_exhaustion_behavior: str = None,
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `default_ignore_list` | `Sequence[str]` | Modules that always get real UUIDs |
| `extend_ignore_list` | `Sequence[str]` | Additional modules to ignore |
| `default_exhaustion_behavior` | `str` | Default exhaustion behavior |

---

## pyproject.toml

```toml
[tool.pytest_uuid]
default_ignore_list = ["sqlalchemy", "celery"]
extend_ignore_list = ["myapp.internal"]
default_exhaustion_behavior = "raise"  # or "cycle" or "random"
```