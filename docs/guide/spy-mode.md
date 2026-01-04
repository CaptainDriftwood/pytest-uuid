# Spy Mode

Spy mode tracks `uuid.uuid4()` calls without mocking them. This is useful when you need to verify UUID generation happens without controlling the output.

## spy_uuid Fixture

The dedicated spy fixture:

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

## Switching to Spy Mode

Use `mock_uuid.spy()` to switch from mocked to real UUIDs mid-test:

```python
import uuid

def test_start_mocked_then_spy(mock_uuid):
    """Start with mocked UUIDs, then switch to real ones."""
    mock_uuid.set("12345678-1234-4678-8234-567812345678")
    first = uuid.uuid4()  # Mocked

    mock_uuid.spy()  # Switch to spy mode
    second = uuid.uuid4()  # Real random UUID

    assert str(first) == "12345678-1234-4678-8234-567812345678"
    assert first != second  # second is random
    assert mock_uuid.mocked_count == 1
    assert mock_uuid.real_count == 1
```

!!! tip "When to use which"
    Use `spy_uuid` when you never need mocking in the test. Use `mock_uuid.spy()` when you need to switch between mocked and real UUIDs within the same test.

## Call Tracking

Both fixtures provide detailed call tracking:

```python
import uuid

def test_call_tracking(spy_uuid):
    first = uuid.uuid4()
    second = uuid.uuid4()

    assert spy_uuid.call_count == 2
    assert spy_uuid.generated_uuids == [first, second]
    assert spy_uuid.last_uuid == second
```

## Call Details

Access detailed metadata for each call:

```python
import uuid

def test_call_details(spy_uuid):
    uuid.uuid4()

    call = spy_uuid.calls[0]
    assert call.uuid is not None
    assert call.was_mocked is False
    assert call.caller_module is not None
    assert call.caller_file is not None
```

## Filtering Calls by Module

```python
import uuid

def test_filter_calls(spy_uuid):
    uuid.uuid4()  # Call from test module
    mymodule.do_something()  # Calls uuid4 internally

    # Filter calls by module prefix
    test_calls = spy_uuid.calls_from("tests")
    module_calls = spy_uuid.calls_from("mymodule")

    assert len(test_calls) == 1
    assert len(module_calls) == 1
```

## Properties

| Property | Description |
|----------|-------------|
| `call_count` | Number of times uuid4 was called |
| `generated_uuids` | List of all generated UUIDs |
| `last_uuid` | Most recently generated UUID |
| `calls` | List of `UUIDCall` records with metadata |

## Methods

| Method | Description |
|--------|-------------|
| `reset()` | Reset tracking data |
| `calls_from(module_prefix)` | Filter calls by module prefix |

## Distinguishing Mocked vs Real Calls

When using `mock_uuid` with ignored modules, track both types:

```python
import uuid

def test_mixed_mocked_and_real(mock_uuid):
    """Track both mocked calls and real calls from ignored modules."""
    mock_uuid.set("12345678-1234-4678-8234-567812345678")
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

## UUIDCall Dataclass

The `UUIDCall` dataclass contains:

| Field | Description |
|-------|-------------|
| `uuid` | The UUID that was returned |
| `was_mocked` | `True` if mocked, `False` if real |
| `caller_module` | Name of the module that made the call |
| `caller_file` | File path where the call originated |