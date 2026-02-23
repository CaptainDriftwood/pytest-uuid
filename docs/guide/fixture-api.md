# Fixture API

The fixture API provides the most flexibility for controlling UUID generation in your tests.

## mock_uuid Fixture

The main fixture for controlling `uuid.uuid4()` calls.

### Basic Usage

```python
import uuid

def test_basic(mock_uuid):
    mock_uuid.set("12345678-1234-4678-8234-567812345678")
    assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
```

### Static UUIDs

Return the same UUID every time:

```python
def test_static(mock_uuid):
    mock_uuid.set("12345678-1234-4678-8234-567812345678")
    assert uuid.uuid4() == uuid.uuid4()  # Same UUID
```

### UUID Sequences

Return UUIDs from a list:

```python
def test_sequence(mock_uuid):
    mock_uuid.set(
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    )
    assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
    # Cycles back by default
    assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
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

### Inspecting the Seed Value

Use the `seed` property to see the actual seed being used:

```python
def test_inspect_seed(mock_uuid):
    mock_uuid.set_seed(42)
    assert mock_uuid.seed == 42

def test_inspect_node_seed(mock_uuid):
    mock_uuid.set_seed_from_node()
    # See the computed seed derived from the test's node ID
    print(f"Using seed: {mock_uuid.seed}")  # e.g., 8427193654
```

!!! tip "Debugging reproducibility"
    The `seed` property is useful for debugging. If a test fails, log the seed value
    so you can reproduce the exact sequence later by passing that seed to `set_seed()`.

### Exhaustion Behavior

Control what happens when a UUID sequence is exhausted:

```python
import uuid
import pytest
from pytest_uuid import UUIDsExhaustedError

def test_exhaustion_raise(mock_uuid):
    mock_uuid.set_exhaustion_behavior("raise")
    mock_uuid.set("11111111-1111-4111-8111-111111111111")

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
    mock_uuid.set("12345678-1234-4678-8234-567812345678")
    mock_uuid.set_ignore("sqlalchemy", "celery")

    # Direct calls are mocked
    assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

    # Calls from sqlalchemy/celery get real UUIDs
```

!!! info "How ignore works"
    The ignore check inspects the entire call stack, not just the immediate caller. If any frame in the call chain is from an ignored module, real UUIDs are returned.

### Reset

Reset the fixture to its initial state:

```python
def test_reset(mock_uuid):
    mock_uuid.set("12345678-1234-4678-8234-567812345678")
    uuid.uuid4()

    mock_uuid.reset()
    # Back to initial state - no UUIDs configured
```

## Additional UUID Versions

The `mock_uuid` fixture provides access to sub-mockers for all UUID versions via properties.

### UUID1 (Time-based with MAC)

```python
import uuid

def test_uuid1_mocked(mock_uuid):
    mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")
    assert str(uuid.uuid1()) == "12345678-1234-1234-8234-567812345678"

def test_uuid1_seeded(mock_uuid):
    mock_uuid.uuid1.set_seed(42)
    first = uuid.uuid1()
    mock_uuid.uuid1.reset()
    mock_uuid.uuid1.set_seed(42)
    assert uuid.uuid1() == first

def test_uuid1_fixed_node(mock_uuid):
    # Return real uuid1 values with a fixed node (MAC address)
    mock_uuid.uuid1.set_node(0x123456789ABC)
    result = uuid.uuid1()
    assert result.node == 0x123456789ABC
```

### UUID3 and UUID5 (Namespace-based)

UUID3 (MD5) and UUID5 (SHA-1) are deterministic, so they only support spy mode:

```python
import uuid

def test_uuid3_tracking(mock_uuid):
    _ = mock_uuid.uuid3  # Initialize spy
    result = uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")

    assert mock_uuid.uuid3.call_count == 1
    assert mock_uuid.uuid3.calls[0].namespace == uuid.NAMESPACE_DNS
    assert mock_uuid.uuid3.calls[0].name == "example.com"

def test_uuid5_filtering(mock_uuid):
    _ = mock_uuid.uuid5
    uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
    uuid.uuid5(uuid.NAMESPACE_URL, "https://example.com")

    dns_calls = mock_uuid.uuid5.calls_with_namespace(uuid.NAMESPACE_DNS)
    assert len(dns_calls) == 1
```

### UUID6, UUID7, UUID8 (RFC 9562)

These require Python 3.14+ or the [uuid6](https://pypi.org/project/uuid6/) package:

```python
from uuid6 import uuid6, uuid7, uuid8  # or from uuid import ... on Python 3.14+

def test_uuid7_mocked(mock_uuid):
    mock_uuid.uuid7.set("12345678-1234-7234-8234-567812345678")
    result = uuid7()
    assert str(result) == "12345678-1234-7234-8234-567812345678"

def test_uuid7_seeded(mock_uuid):
    mock_uuid.uuid7.set_seed(42)
    first = uuid7()
    mock_uuid.uuid7.reset()
    mock_uuid.uuid7.set_seed(42)
    assert uuid7() == first
```

### Independent Call Tracking

Each UUID version is tracked independently:

```python
def test_all_versions_independent(mock_uuid):
    mock_uuid.set("44444444-4444-4444-8444-444444444444")  # uuid4
    mock_uuid.uuid1.set("11111111-1111-1111-8111-111111111111")

    uuid.uuid4()
    uuid.uuid4()
    uuid.uuid1()

    assert mock_uuid.call_count == 2      # uuid4 only
    assert mock_uuid.uuid1.call_count == 1
```

---

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
        mocker.set("12345678-1234-4678-8234-567812345678")
        user = create_user()
        assert user["id"] == "12345678-1234-4678-8234-567812345678"
```

### Mocking Default-Ignored Packages

By default, packages like `botocore` are ignored. Use `ignore_defaults=False` to mock them:

```python
def test_mock_botocore(mock_uuid_factory):
    with mock_uuid_factory("botocore.handlers", ignore_defaults=False) as mocker:
        mocker.set("12345678-1234-4678-8234-567812345678")
        # botocore will now receive mocked UUIDs
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