# Configuration

pytest-uuid can be configured globally via `pyproject.toml` or programmatically in `conftest.py`.

## pyproject.toml

```toml
[tool.pytest_uuid]
default_ignore_list = ["sqlalchemy", "celery"]
extend_ignore_list = ["myapp.internal"]
default_exhaustion_behavior = "raise"
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_ignore_list` | `list[str]` | `["botocore"]` | Modules that always receive real UUIDs |
| `extend_ignore_list` | `list[str]` | `[]` | Additional modules to add to ignore list |
| `default_exhaustion_behavior` | `str` | `"cycle"` | Default behavior when UUIDs exhausted |

!!! note "Default Ignore List"
    By default, `botocore` is ignored because it uses `uuid.uuid4()` internally for generating idempotent ClientTokens in AWS API operations. Patching this can interfere with AWS SDK retry logic. Use `extend_ignore_list` to add additional packages without overriding this default.

!!! tip "Opting Out of Defaults Per-Test"
    If you need to mock packages in the default ignore list for a specific test, use the `ignore_defaults=False` parameter:

    ```python
    @pytest.mark.freeze_uuid("...", ignore_defaults=False)
    def test_mock_botocore():
        # botocore will now receive mocked UUIDs
        pass
    ```

    See the [Decorator API](decorator-api.md#opting-out-of-default-ignores) or [Marker API](marker-api.md#opting-out-of-default-ignores) for more details.

## Programmatic Configuration

Configure in `conftest.py`:

```python
# conftest.py
import pytest_uuid

pytest_uuid.configure(
    default_ignore_list=["sqlalchemy", "celery"],
    extend_ignore_list=["myapp.internal"],
    default_exhaustion_behavior="raise",
)
```

## Ignore List

The ignore list specifies module prefixes that should receive real UUIDs even when mocking is active. This is useful for third-party libraries that depend on real UUIDs for internal operations.

### Common Modules to Ignore

```toml
[tool.pytest_uuid]
default_ignore_list = [
    "sqlalchemy",      # ORM with UUID primary keys
    "celery",          # Task queue with UUID task IDs
    "alembic",         # Database migrations
    "django",          # Web framework internals
]
```

### How Ignore Works

The ignore check inspects the entire call stack:

1. When `uuid.uuid4()` is called, pytest-uuid walks the call stack
2. If any frame is from a module matching an ignored prefix, a real UUID is returned
3. This handles cases where your code calls a library that internally calls `uuid.uuid4()`

```python
def test_ignore_in_stack(mock_uuid):
    mock_uuid.set("12345678-1234-5678-1234-567812345678")
    mock_uuid.set_ignore("sqlalchemy")

    # Your code calls SQLAlchemy, which calls uuid.uuid4()
    # SQLAlchemy gets a real UUID because it's in the call stack
    session.add(User(name="Alice"))
```

## Exhaustion Behavior

Control what happens when a UUID sequence runs out:

| Behavior | Description |
|----------|-------------|
| `"cycle"` | Loop back to the start of the sequence (default) |
| `"random"` | Generate random UUIDs |
| `"raise"` | Raise `UUIDsExhaustedError` |

### Example: Strict Mode

For strict testing, raise an error when UUIDs are exhausted:

```toml
[tool.pytest_uuid]
default_exhaustion_behavior = "raise"
```

```python
import uuid
import pytest
from pytest_uuid import UUIDsExhaustedError

def test_strict(mock_uuid):
    mock_uuid.set("11111111-1111-1111-1111-111111111111")

    uuid.uuid4()  # OK

    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()  # Fails - must provide enough UUIDs
```

## Per-Test Override

Configuration can be overridden per-test:

```python
import uuid
import pytest

# Global config: on_exhausted="raise"

@pytest.mark.freeze_uuid(
    "11111111-1111-1111-1111-111111111111",
    on_exhausted="cycle",  # Override for this test
)
def test_with_override():
    uuid.uuid4()
    uuid.uuid4()  # Cycles instead of raising
```

## Environment Variables

Currently, pytest-uuid does not support environment variables for configuration. Use `pyproject.toml` or `conftest.py` instead.