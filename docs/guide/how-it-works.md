# How It Works

pytest-uuid provides seamless UUID mocking that "just works" with both import patterns:

```python
import uuid
uuid.uuid4()  # Mocked

from uuid import uuid4
uuid4()  # Also mocked
```

This page explains how pytest-uuid achieves this, and why it uses a proxy-based approach.

## The Challenge: Python's Import System

When you write `from uuid import uuid4`, Python creates a **direct reference** to the function in your module's namespace:

```python
# mymodule.py
from uuid import uuid4  # mymodule.uuid4 -> uuid.uuid4 (at import time)

def generate_id():
    return uuid4()  # Calls mymodule.uuid4, NOT uuid.uuid4
```

If a mocking library only patches `uuid.uuid4`, modules that used `from uuid import uuid4` still have their original reference—they bypass the mock entirely.

### How Other Libraries Handle This

Most mocking libraries (unittest.mock, pytest-mock) require you to **patch where it's used**:

```python
# You must know and patch every location
mocker.patch("mymodule.uuid4", return_value=...)
mocker.patch("other_module.uuid4", return_value=...)
```

This is explicit and predictable, but requires you to know every module that imports `uuid4`.

### pytest-uuid's Approach

pytest-uuid takes a different philosophy: **patch once, work everywhere**. When the plugin loads, it installs a permanent proxy at `uuid.uuid4`. Any code that imports `uuid4`—whether before or after the proxy is installed—gets this proxy function.

## The Solution: Permanent Proxy

pytest-uuid uses a **proxy function** that replaces `uuid.uuid4` at plugin initialization:

```
┌─────────────────────────────────────────────────────────┐
│  Plugin Load (pytest_load_initial_conftests)            │
│                                                         │
│  1. Save original uuid.uuid4 function                   │
│  2. Replace uuid.uuid4 with proxy function              │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Any Code (conftest.py, test files, production code)   │
│                                                         │
│  from uuid import uuid4  # Gets the proxy!              │
│  uuid4()  # Calls proxy, not original                   │
└─────────────────────────────────────────────────────────┘
```

### Why This Works

The proxy is installed in `pytest_load_initial_conftests`, which runs **before** conftest files are loaded. This means:

1. When conftest.py does `from uuid import uuid4`, it gets the proxy
2. When test files do `from uuid import uuid4`, they get the proxy
3. When production code is imported and does `from uuid import uuid4`, it gets the proxy
4. Even Pydantic models with `default_factory=uuid4` capture the proxy

### How the Proxy Works

```python
# Simplified version of what happens in _proxy.py

_original_uuid4 = None
_generator_stack = []  # Thread-safe stack of generators
_generator_lock = threading.Lock()

def _proxy_uuid4():
    with _generator_lock:
        if _generator_stack:
            generator = _generator_stack[-1]

    if generator is not None:
        return generator()  # Use the test generator

    return _original_uuid4()  # Use real uuid4

def install_proxy():
    global _original_uuid4
    _original_uuid4 = uuid.uuid4
    uuid.uuid4 = _proxy_uuid4
```

When you use `freeze_uuid`:

1. `__enter__` pushes a generator onto the stack
2. All `uuid.uuid4()` calls go through the proxy → generator
3. `__exit__` pops the generator from the stack

### Call Flow

```
Test code calls uuid4()
         │
         ▼
    uuid.uuid4  (actually the proxy)
         │
         ▼
    Generator stack check
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Generator   Original
 active?    uuid.uuid4
    │
    ▼
Return deterministic UUID
```

## Thread Safety

The proxy uses a **thread-safe global stack** protected by a lock:

- All threads see the same active generator
- Lock protects stack operations (push/pop/read)
- Generator is called outside the lock to avoid holding it during user code

For parallel test execution with pytest-xdist, each worker is a separate process with its own proxy and stack, so there's no cross-worker interference.

!!! warning "Concurrent UUID Generation"
    If your test code itself spawns threads that call `uuid.uuid4()` concurrently, all threads will use the same generator. The UUID values will still be deterministic (from the generator), but the order in which threads receive UUIDs depends on thread scheduling.

## Nested Contexts

The stack-based approach supports nested `freeze_uuid` contexts:

```python
with freeze_uuid(seed=42):
    uuid.uuid4()  # Uses seed=42 generator

    with freeze_uuid(seed=99):
        uuid.uuid4()  # Uses seed=99 generator (inner)

    uuid.uuid4()  # Back to seed=42 generator
```

Each context pushes its generator onto the stack; `__exit__` pops it off.

## Compatibility

The proxy approach is compatible with common testing libraries:

| Library | Compatible | Notes |
|---------|------------|-------|
| moto | Yes | Uses decorator/context manager patching |
| freezegun | Yes | Patches loaded modules |
| responses | Yes | Socket-level patching |
| pytest-mock | Yes | Thin wrapper over unittest.mock |
| httpretty | Yes | Socket-level patching |
| Pydantic | Yes | `default_factory=uuid4` works correctly |

The proxy coexists peacefully with other mocking tools because it only affects `uuid.uuid4` and delegates to the original when not in a freeze context.

## Advantages Over Import Hook

Previous versions of pytest-uuid used an import hook to intercept module imports and patch `uuid4` references. The proxy approach offers several advantages:

| Aspect | Import Hook | Proxy |
|--------|-------------|-------|
| Complexity | ~200 lines, wraps `builtins.__import__` | ~100 lines, simple delegation |
| Edge cases | Stale patches, late imports | None—proxy handles all cases |
| Pydantic | Required special handling | Works automatically |
| Performance | Scanned every import | Zero overhead per import |
| Debugging | Complex stack traces | Simple stack traces |

## Summary

| Technique | Purpose |
|-----------|---------|
| Permanent proxy | Replace `uuid.uuid4` once at plugin load |
| Thread-safe stack | Support nested contexts and thread safety |
| Early hook | Install proxy before conftest loads |

This combination ensures that `freeze_uuid` "just works" regardless of how or when modules import `uuid4`.

## Further Reading

- [Source code: `_proxy.py`](https://github.com/CaptainDriftwood/pytest-uuid/blob/master/src/pytest_uuid/_proxy.py) - The proxy implementation
- [Source code: `plugin.py`](https://github.com/CaptainDriftwood/pytest-uuid/blob/master/src/pytest_uuid/plugin.py) - Plugin hooks and fixtures
