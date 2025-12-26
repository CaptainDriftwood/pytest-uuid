# pytest-uuid Design Document

> This document captures the design research and proposals for enhancing pytest-uuid.
> Created: 2025-12-26

## Background

The user requested enhancements to pytest-uuid inspired by [freezegun](https://github.com/spulec/freezegun) and [pytest-freezegun](https://pypi.org/project/pytest-freezegun/). The goal is to provide a more flexible and powerful API for mocking `uuid.uuid4()` in tests.

## Research Summary

### Freezegun's Key Patterns

Based on research of freezegun, pytest-freezegun, and pytest-freezer:

1. **Decorator API**: `@freeze_time("2012-01-14")` - simple, declarative
2. **Ignore list**: Global config + per-invocation override via `ignore=["package.name"]`
3. **Fixture integration**: `freezer` fixture that returns a controller object
4. **Marker support**: `@pytest.mark.freeze_time` for pytest-native decoration

### Freezegun Ignore Implementation

Freezegun implements ignore lists by:
- Maintaining a global stack of ignore tuples
- Walking the call stack to check if caller's module should be ignored
- Skipping ignored modules during patching

```python
# How freezegun checks if a module should use real time
def _should_use_real_time():
    frame = inspect.currentframe().f_back.f_back
    for _ in range(call_stack_inspection_limit):
        module_name = frame.f_globals.get('__name__')
        if module_name and module_name.startswith(ignore_lists[-1]):
            return True
```

---

## Design Proposal for pytest-uuid

### 1. Mocking Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **static** | Same UUID returned every call | Deterministic tests needing one ID |
| **sequence** | List of UUIDs, with exhaustion behavior | Testing ordered operations |
| **seeded** | Random but reproducible via seed | Reproducible "random" tests |
| **node-seeded** | Seed derived from pytest node ID | Auto-reproducible per test |

### 2. Sequence Exhaustion Behavior

```python
from enum import Enum

class ExhaustionBehavior(Enum):
    CYCLE = "cycle"       # Loop back to start (current behavior)
    RANDOM = "random"     # Fall back to random UUIDs
    RAISE = "raise"       # Raise UUIDExhaustedError
```

**Recommendation**: Default to `CYCLE` for backwards compatibility, but `RAISE` is safest for catching bugs.

### 3. Proposed API

#### Decorator API

```python
from pytest_uuid import freeze_uuid

# Static - same UUID every time
@freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_static():
    assert uuid.uuid4() == UUID("12345678-...")
    assert uuid.uuid4() == UUID("12345678-...")  # Same!

# Sequence with cycling
@freeze_uuid(["uuid1", "uuid2"], on_exhausted="cycle")
def test_sequence():
    ...

# Sequence that raises when exhausted
@freeze_uuid(["uuid1", "uuid2"], on_exhausted="raise")
def test_strict_sequence():
    ...

# Seeded random
@freeze_uuid(seed=42)
def test_seeded():
    ...

# Node-seeded (auto-reproducible)
@freeze_uuid(seed="node")
def test_node_seeded():
    ...

# Ignore specific packages
@freeze_uuid("...", ignore=["sqlalchemy", "myapp.models"])
def test_with_ignores():
    ...
```

#### Marker API (pytest-native)

```python
@pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
def test_with_marker():
    ...

@pytest.mark.freeze_uuid(seed="node")
def test_node_seeded():
    ...
```

#### Fixture API (enhanced)

```python
def test_with_fixture(mock_uuid):
    # Current API still works (backwards compatible)
    mock_uuid.set("uuid1", "uuid2")
    mock_uuid.set_default("...")

    # New methods
    mock_uuid.set_seed(42)
    mock_uuid.set_seed_from_node()  # Uses current test's node ID
    mock_uuid.on_exhausted("raise")  # Change exhaustion behavior

def test_with_freezer(uuid_freezer):
    # Alternative fixture name matching freezegun pattern
    uuid_freezer.freeze("12345678-...")
    uuid_freezer.freeze_sequence(["a", "b", "c"])
    uuid_freezer.freeze_seeded(seed=42)
```

### 4. Ignore Packages Implementation

```python
# Global configuration (like freezegun.configure)
import pytest_uuid

pytest_uuid.configure(
    default_ignore_list=["sqlalchemy", "celery"],
    extend_ignore_list=["myapp.internal"],
)

# Per-test override
@freeze_uuid("...", ignore=["extra.package"])
def test_something():
    ...
```

**How it works:**
- When patching, skip modules whose `__name__` starts with any ignore prefix
- Check call stack to avoid mocking when called from ignored module

### 5. Seeded UUID Generation

#### Implementation

```python
import random
import uuid

def _generate_uuid_from_random(rng: random.Random) -> uuid.UUID:
    """Generate a UUID v4 using a seeded Random instance."""
    random_bits = rng.getrandbits(128)
    # Set version to 4 and variant to RFC 4122
    random_bits = (random_bits & ~(0xf << 76)) | (4 << 76)  # version 4
    random_bits = (random_bits & ~(0x3 << 62)) | (0x2 << 62)  # variant
    return uuid.UUID(int=random_bits)
```

#### Seed Parameter: `int` vs `random.Random`

The `seed` parameter accepts both types:

```python
seed: int | random.Random | Literal["node"] | None = None
```

**Integer Seed:**
```python
@freeze_uuid(seed=42)
def test_a():
    result = uuid.uuid4()  # Always the SAME "first" UUID from seed 42

@freeze_uuid(seed=42)
def test_b():
    result = uuid.uuid4()  # Identical to test_a - fresh Random(42) each time
```

- Creates a **fresh** `random.Random(seed)` internally each time
- State always starts at the same point
- Simple and declarative

**random.Random Instance (Bring Your Own Randomizer):**
```python
rng = random.Random(42)
rng.random()  # Advance the state once

@freeze_uuid(seed=rng)
def test_c():
    result = uuid.uuid4()  # Gets the SECOND UUID from seed 42's sequence
```

- User controls the **exact state** of the randomizer
- Can pre-advance, share between fixtures, or use a subclass
- Useful for:
  - Pre-advanced state (skip first N UUIDs)
  - Shared state across fixtures/tests
  - Custom Random subclass with different PRNG algorithm
  - Injecting a mock Random for testing

| Approach | State | Use Case |
|----------|-------|----------|
| `seed=42` | Fresh every time | "I want reproducible UUIDs" |
| `seed=random.Random(42)` | User-controlled | "I need control over the random state" |

### 7. Node-Seeded Implementation

```python
import hashlib
import pytest

def _get_node_seed(request: pytest.FixtureRequest) -> int:
    """Generate deterministic seed from test node ID."""
    node_id = request.node.nodeid  # e.g., "tests/test_foo.py::TestClass::test_method"
    return int(hashlib.md5(node_id.encode()).hexdigest()[:8], 16)
```

**Benefits:**
- Same test always gets same UUIDs
- Different tests get different UUIDs
- No explicit seed management needed
- Failures are reproducible

### 8. Proposed File Structure

```
src/pytest_uuid/
├── __init__.py          # Public API exports
├── plugin.py            # Pytest plugin (fixtures, hooks)
├── api.py               # Core UUIDMocker, freeze_uuid decorator
├── config.py            # Global configuration (ignore lists)
└── generators.py        # UUID generation strategies (static, seeded, etc.)
```

---

## Open Questions

1. **Exhaustion default**: Should the default be `cycle` (backwards compatible) or `raise` (safer)?

2. **Fixture naming**: Keep `mock_uuid` or add `uuid_freezer` as an alias/alternative?

3. **Marker name**: `@pytest.mark.freeze_uuid` or `@pytest.mark.mock_uuid`?

4. **Seed scope**: Should `seed="node"` be the recommended default for most users?

5. **Breaking changes**: Is it okay to change the default `on_exhausted` behavior in a minor version, or should we wait for 1.0?

---

## Current Implementation Status

As of the initial implementation:

- `mock_uuid` fixture provides basic mocking with `set()`, `set_default()`, `reset()`
- Supports both `import uuid` and `from uuid import uuid4` patterns
- Uses pytest's `monkeypatch` for clean teardown
- `mock_uuid_factory` provides module-specific patching

---

## References

- [freezegun GitHub](https://github.com/spulec/freezegun)
- [pytest-freezegun PyPI](https://pypi.org/project/pytest-freezegun/)
- [pytest-freezer PyPI](https://pypi.org/project/pytest-freezer/)
- [pytest-freezer GitHub](https://github.com/pytest-dev/pytest-freezer)
- [Freezegun Guide](https://pytest-with-eric.com/plugins/python-freezegun/)
