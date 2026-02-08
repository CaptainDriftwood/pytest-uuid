# How It Works

pytest-uuid provides seamless UUID mocking that "just works" with both import patterns:

```python
import uuid
uuid.uuid4()  # Mocked

from uuid import uuid4
uuid4()  # Also mocked
```

This page explains how pytest-uuid achieves this, and why it uses techniques that differ from typical pytest mocking plugins.

## The Challenge: Python's Import System

When you write `from uuid import uuid4`, Python creates a **direct reference** to the function in your module's namespace:

```python
# mymodule.py
from uuid import uuid4  # mymodule.uuid4 -> uuid.uuid4 (at import time)

def generate_id():
    return uuid4()  # Calls mymodule.uuid4, NOT uuid.uuid4
```

If pytest-uuid only patches `uuid.uuid4`, modules that used `from uuid import uuid4` still have their original reference—they bypass the mock entirely.

### How Other Libraries Handle This

Most mocking libraries (unittest.mock, pytest-mock) require you to **patch where it's used**:

```python
# You must know and patch every location
mocker.patch("mymodule.uuid4", return_value=...)
mocker.patch("other_module.uuid4", return_value=...)
```

This is explicit and predictable, but requires you to know every module that imports `uuid4`.

### pytest-uuid's Approach

pytest-uuid takes a different philosophy: **patch everywhere automatically**. When you use `freeze_uuid` or `mock_uuid`, the plugin:

1. Patches `uuid.uuid4` directly
2. Scans `sys.modules` to find all modules that imported `uuid4`
3. Patches each module's reference

This is more convenient but creates a challenge: **what about modules imported during the freeze context?**

## The Late Import Problem

Consider this scenario:

```python
@freeze_uuid(seed=42)
def test_something():
    from myapp import models  # Imported AFTER freeze_uuid started
    models.create_user()      # Does this get mocked UUIDs?
```

When `myapp.models` is imported, its `from uuid import uuid4` statement executes. At that moment, `uuid.uuid4` is already patched—so the module gets the patched function. Great!

But here's the problem: **pytest caches modules in `sys.modules`**. If a later test runs with a different freeze context:

```python
@freeze_uuid(seed=99)  # Different context
def test_other():
    from myapp import models  # Cache hit - no reimport!
    models.create_user()      # Still has uuid4 from seed=42 context!
```

The module's `uuid4` reference is now **stale**—it points to the old patched function from the previous test.

### Why This Causes Flaky Tests

With pytest-xdist or randomized test ordering:

- Different test orderings cause different modules to be imported first
- Stale references cause non-deterministic UUID generation
- Tests pass in isolation but fail when run together

## The Solution: Import Hook

pytest-uuid uses an **import hook** to intercept module imports during a freeze context. When a module is imported:

1. The hook detects it (by comparing `sys.modules` before/after import)
2. Scans the new module for `uuid4` references
3. Patches them immediately
4. Tracks them for cleanup when the context exits

Additionally, the plugin uses **marker-based detection** to identify stale patches from previous contexts and re-patch them.

### How the Import Hook Works

```python
# Simplified version of what happens in _import_hook.py

class UUIDImportHook:
    def install(self):
        self._original_import = builtins.__import__
        builtins.__import__ = self._patching_import

    def _patching_import(self, name, ...):
        modules_before = set(sys.modules.keys())
        result = self._original_import(name, ...)
        modules_after = set(sys.modules.keys())

        # Patch uuid4 in any newly imported modules
        for module_name in (modules_after - modules_before):
            self._patch_module(sys.modules[module_name])

        return result
```

### Is This Unusual?

Yes. Most pytest plugins don't wrap `builtins.__import__`. They either:

- Require explicit patching (pytest-mock)
- Only patch already-loaded modules (similar to freezegun's approach)
- Work at a lower level that doesn't involve imports (responses, httpretty)

pytest-uuid chose comprehensive automatic patching over requiring users to understand import mechanics. The tradeoff is a more invasive implementation.

## Compatibility

The import hook is compatible with common testing libraries:

| Library | Compatible | Notes |
|---------|------------|-------|
| moto | Yes | Uses decorator/context manager patching, no import hooks |
| freezegun | Yes | Patches loaded modules, no import hooks |
| responses | Yes | Socket-level patching |
| pytest-mock | Yes | Thin wrapper over unittest.mock |
| httpretty | Yes | Socket-level patching |

The only theoretical conflict would be with another library that also wraps `builtins.__import__` AND contexts are exited in the wrong (non-LIFO) order. No common libraries do this.

!!! note "LIFO Context Nesting"
    When using multiple context managers that wrap `builtins.__import__`, they must be exited in reverse order (Last In, First Out). Normal `with` statement nesting guarantees this automatically.

## Thread Safety

The import hook (and pytest-uuid generally) is **not thread-safe**. This is acceptable for pytest's sequential execution model.

For parallel test execution with pytest-xdist, each worker is a separate process with its own `sys.modules`, so there's no cross-worker interference within the import hook mechanism.

!!! warning "Concurrent UUID Generation"
    If your test code itself spawns threads that call `uuid.uuid4()` concurrently, the call tracking may have race conditions. The UUID values themselves will still be deterministic (from the generator), but call metadata tracking is not synchronized.

## Summary

| Technique | Purpose |
|-----------|---------|
| Patch `uuid.uuid4` | Handle `import uuid; uuid.uuid4()` |
| Scan `sys.modules` | Find modules with `from uuid import uuid4` |
| Import hook | Catch modules imported during freeze context |
| Marker detection | Identify and re-patch stale references |

This combination ensures that `freeze_uuid` "just works" regardless of how or when modules import `uuid4`.

## Further Reading

- [Source code: `_import_hook.py`](https://github.com/CaptainDriftwood/pytest-uuid/blob/master/src/pytest_uuid/_import_hook.py) - The import hook implementation
- [Source code: `_tracking.py`](https://github.com/CaptainDriftwood/pytest-uuid/blob/master/src/pytest_uuid/_tracking.py) - Module scanning and stale patch detection