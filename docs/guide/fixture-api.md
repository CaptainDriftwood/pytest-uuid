# Fixture API

The fixture API provides the most flexibility for controlling UUID generation in your tests.

## mock_uuid Fixture

The main fixture for controlling `uuid.uuid4()` calls.

### Basic Usage

```python
import uuid

def test_basic(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
```

### Static UUIDs

Return the same UUID every time:

```python
def test_static(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
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
```

### Node-Seeded UUIDs

Derive the seed from the test's node ID:

```python
def test_node_seeded(mock_uuid):
    mock_uuid.set_seed_from_node()
    # Same test always produces the same sequence
```

### Exhaustion Behavior

Control what happens when a UUID sequence is exhausted:

```python
from pytest_uuid import UUIDsExhaustedError

def test_exhaustion_raise(mock_uuid):
    mock_uuid.set_exhaustion_behavior("raise")
    mock_uuid.set("11111111-1111-1111-1111-111111111111")

    uuid.uuid4()  # Returns the UUID

    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()  # Raises - sequence exhausted
```

Exhaustion behaviors:

- `"cycle"` (default): Loop back to the start of the sequence
- `"random"`: Fall back to generating random UUIDs
- `"raise"`: Raise `UUIDsExhaustedError`

### Ignoring Modules

Exclude specific packages from UUID mocking:

```python
def test_with_ignored_modules(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    mock_uuid.set_ignore("sqlalchemy", "celery")

    # Direct calls are mocked
    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    # Calls from sqlalchemy/celery get real UUIDs
```

!!! info "How ignore works"
    The ignore check inspects the entire call stack, not just the immediate caller. If any frame in the call chain is from an ignored module, real UUIDs are returned.

### Reset

Reset the fixture to its initial state:

```python
def test_reset(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    uuid.uuid4()

    mock_uuid.reset()
    # Back to initial state - no UUIDs configured
```

## mock_uuid_factory Fixture

For module-specific mocking:

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

## Methods Reference

| Method | Description |
|--------|-------------|
| `set(*uuids)` | Set one or more UUIDs to return (cycles by default) |
| `set_default(uuid)` | Set a default UUID for all calls |
| `set_seed(seed)` | Set a seed for reproducible generation |
| `set_seed_from_node()` | Use test node ID as seed |
| `set_exhaustion_behavior(behavior)` | Set behavior when sequence exhausted |
| `spy()` | Switch to spy mode (return real UUIDs while tracking) |
| `reset()` | Reset to initial state |
| `set_ignore(*module_prefixes)` | Set modules to ignore |