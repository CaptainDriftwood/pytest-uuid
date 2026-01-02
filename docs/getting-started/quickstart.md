# Quick Start

This guide will get you up and running with pytest-uuid in minutes.

## Basic Usage

The simplest way to use pytest-uuid is with the `mock_uuid` fixture:

```python
import uuid

def test_single_uuid(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

## Multiple UUIDs

Return different UUIDs for each call:

```python
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

## Using Decorators

If you prefer decorators over fixtures:

```python
import uuid
from pytest_uuid import freeze_uuid

@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_with_decorator():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

## Using Markers

Or use pytest markers for configuration:

```python
import uuid
import pytest

@pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_with_marker():
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

## Seeded UUIDs

For reproducible but not hardcoded UUIDs, use seeding:

```python
import uuid
from pytest_uuid import freeze_uuid

@freeze_uuid(seed=42)
def test_seeded():
    # Same seed always produces the same UUIDs
    result = uuid.uuid4()
    assert result.version == 4
```

## Node-Seeded UUIDs (Recommended)

The recommended approach - each test gets deterministic UUIDs based on its name:

```python
import uuid
import pytest

@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded():
    # This test always produces the same UUIDs
    # Different tests get different sequences
    result = uuid.uuid4()
    assert result.version == 4
```

!!! tip "Why node seeding?"
    Node-seeded UUIDs give you deterministic, reproducible tests without hardcoding values. Each test gets its own unique seed derived from its fully-qualified name, so tests are isolated and debugging is easy.

## Next Steps

- [Fixture API](../guide/fixture-api.md) - Full fixture documentation
- [Decorator API](../guide/decorator-api.md) - Using `@freeze_uuid`
- [Marker API](../guide/marker-api.md) - Using `@pytest.mark.freeze_uuid`
- [Spy Mode](../guide/spy-mode.md) - Track calls without mocking