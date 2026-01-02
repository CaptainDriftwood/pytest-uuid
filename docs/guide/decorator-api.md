# Decorator API

The `@freeze_uuid` decorator provides a clean way to configure UUID mocking at the function or class level.

## Basic Usage

```python
import uuid
from pytest_uuid import freeze_uuid

@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_with_decorator():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

## Multiple UUIDs

Pass multiple UUIDs as a list:

```python
@freeze_uuid([
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
])
def test_sequence():
    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
```

## Seeded UUIDs

Use a seed for reproducible UUIDs:

```python
@freeze_uuid(seed=42)
def test_seeded():
    result = uuid.uuid4()
    assert result.version == 4
```

## Custom Random Generator

Pass your own `random.Random` instance:

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

## Exhaustion Behavior

Control what happens when UUIDs are exhausted:

```python
import uuid
import pytest
from pytest_uuid import freeze_uuid, UUIDsExhaustedError

@freeze_uuid(
    ["11111111-1111-1111-1111-111111111111"],
    on_exhausted="raise",
)
def test_exhaustion():
    uuid.uuid4()  # OK
    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()  # Raises
```

Options:

- `"cycle"` (default): Loop back to the start
- `"random"`: Generate random UUIDs
- `"raise"`: Raise `UUIDsExhaustedError`

## Ignoring Modules

Exclude modules from mocking:

```python
@freeze_uuid("12345678-1234-5678-1234-567812345678", ignore=["sqlalchemy"])
def test_with_ignored():
    # Direct calls are mocked
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
    # Calls from sqlalchemy get real UUIDs
```

## Class-Level Decorator

Apply to all methods in a test class:

```python
@freeze_uuid("12345678-1234-5678-1234-567812345678")
class TestUserService:
    def test_create(self):
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    def test_update(self):
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

## Context Manager

Use `freeze_uuid` as a context manager for fine-grained control:

```python
def test_context_manager():
    with freeze_uuid("12345678-1234-5678-1234-567812345678"):
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    # Original uuid.uuid4 is restored
    assert uuid.uuid4() != uuid.UUID("12345678-1234-5678-1234-567812345678")
```

Access the freezer inside the context:

```python
def test_with_freezer():
    with freeze_uuid("12345678-1234-5678-1234-567812345678") as freezer:
        uuid.uuid4()
        freezer.reset()  # Reset mid-test
        uuid.uuid4()
```

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `uuids` | `str`, `UUID`, or sequence | UUID(s) to return |
| `seed` | `int`, `Random`, or `"node"` | Seed for reproducible generation |
| `on_exhausted` | `str` | `"cycle"`, `"random"`, or `"raise"` |
| `ignore` | `list[str]` | Module prefixes to exclude from mocking |