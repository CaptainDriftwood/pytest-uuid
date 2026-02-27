"""Permanent proxies for UUID functions that enable context-aware mocking.

This module implements a proxy-based patching approach that solves several
edge cases with the traditional attribute-patching approach:

1. Pydantic default_factory=uuid4 - captures function at class definition
2. Late imports during freeze_uuid context - stale patched functions
3. Closures and data structures storing uuid function references

Architecture:
    1. At plugin load (pytest_configure), install proxies for all uuid functions
    2. Any code that imports uuid functions (before or after) gets the proxy
    3. The proxy checks a thread-safe stack for the current generator
    4. If a generator is set, use it; otherwise, call original function

Thread Safety:
    Uses thread-safe global stacks protected by a lock. This ensures:
    - All threads see the same active generator (unlike ContextVar)
    - Nested contexts work correctly (stack-based)
    - Thread-safe access to the generator stacks

Supported UUID Functions:
    - uuid1: Time-based with MAC address (all Python versions)
    - uuid3: MD5 namespace hash (all Python versions)
    - uuid4: Random (all Python versions)
    - uuid5: SHA-1 namespace hash (all Python versions)
    - uuid6: Reordered time-based (Python 3.14+ or uuid6 package)
    - uuid7: Unix timestamp-based (Python 3.14+ or uuid6 package)
    - uuid8: Custom format (Python 3.14+ or uuid6 package)

Usage:
    # At plugin initialization (once)
    install_proxy()

    # In freeze_uuid.__enter__
    token = set_generator(my_patched_uuid4, func_name="uuid4")

    # In freeze_uuid.__exit__
    reset_generator(token)
"""

from __future__ import annotations

import threading
import uuid
from typing import Any, Callable

from pytest_uuid._compat import HAS_UUID6_7_8

# Type alias for UUID generator functions
UUIDGenerator = Callable[..., uuid.UUID]

# All supported UUID function names
UUID_FUNC_NAMES = ("uuid1", "uuid3", "uuid4", "uuid5", "uuid6", "uuid7", "uuid8")

# Functions available in all Python versions (stdlib)
STDLIB_UUID_FUNCS = ("uuid1", "uuid3", "uuid4", "uuid5")

# Functions that require Python 3.14+ or uuid6 package
EXTENDED_UUID_FUNCS = ("uuid6", "uuid7", "uuid8")

# Original UUID functions, captured before any patching
# Key: function name (e.g., "uuid4"), Value: original function
_originals: dict[str, UUIDGenerator] = {}

# Thread-safe stacks of generators, protected by a lock
# Key: function name, Value: list of generators (innermost at end)
_generator_stacks: dict[str, list[UUIDGenerator]] = {
    name: [] for name in UUID_FUNC_NAMES
}
_generator_lock = threading.Lock()

# Track whether the proxy has been installed
_proxy_installed: bool = False


def _create_proxy(func_name: str) -> Callable[..., uuid.UUID]:
    """Create a proxy function for a specific UUID function.

    Args:
        func_name: The name of the UUID function (e.g., "uuid4").

    Returns:
        A proxy function that delegates to the current generator or original.
    """

    def proxy(*args: Any, **kwargs: Any) -> uuid.UUID:
        generator = None
        with _generator_lock:
            stack = _generator_stacks.get(func_name)
            if stack:
                generator = stack[-1]
        if generator is not None:
            # Call outside lock to avoid holding lock during user code
            return generator(*args, **kwargs)
        # Fall back to original function
        original = _originals.get(func_name)
        if original is None:
            raise RuntimeError(
                f"Proxy for {func_name} called before installation. "
                f"Ensure pytest-uuid plugin is loaded."
            )
        return original(*args, **kwargs)

    # Preserve function metadata for debugging
    proxy.__name__ = f"_proxy_{func_name}"
    proxy.__qualname__ = f"_proxy_{func_name}"
    proxy.__doc__ = f"Proxy for uuid.{func_name}() that enables context-aware mocking."

    return proxy


def install_proxy() -> None:
    """Install proxies for all supported UUID functions.

    This should be called once at plugin initialization (pytest_configure).
    It replaces uuid.uuid1, uuid.uuid3, uuid.uuid4, uuid.uuid5 with proxies,
    and uuid.uuid6, uuid.uuid7, uuid.uuid8 if available.

    The proxy is idempotent - calling multiple times is safe.
    """
    global _proxy_installed

    if _proxy_installed:
        return

    # Install proxies for stdlib functions (always available)
    for func_name in STDLIB_UUID_FUNCS:
        original = getattr(uuid, func_name)
        _originals[func_name] = original
        setattr(uuid, func_name, _create_proxy(func_name))

    # Install proxies for extended functions (Python 3.14+ or uuid6 package)
    if HAS_UUID6_7_8:
        for func_name in EXTENDED_UUID_FUNCS:
            if hasattr(uuid, func_name):
                # Python 3.14+ - use stdlib
                original = getattr(uuid, func_name)
                _originals[func_name] = original
                setattr(uuid, func_name, _create_proxy(func_name))
            else:
                # Python < 3.14 with uuid6 package - import from uuid6
                from pytest_uuid._compat import uuid6, uuid7, uuid8

                func_map = {"uuid6": uuid6, "uuid7": uuid7, "uuid8": uuid8}
                original = func_map.get(func_name)
                if original is not None:
                    _originals[func_name] = original
                    # Also patch the uuid6 module so direct imports get the proxy
                    try:
                        import uuid6 as uuid6_module

                        setattr(uuid6_module, func_name, _create_proxy(func_name))
                    except ImportError:
                        pass  # uuid6 package not available

    _proxy_installed = True


def uninstall_proxy() -> None:
    """Restore the original UUID functions.

    This is primarily for testing the proxy itself.
    In normal usage, the proxy stays installed for the pytest session.
    """
    global _proxy_installed

    if not _proxy_installed:
        return

    # Restore stdlib functions
    for func_name in STDLIB_UUID_FUNCS:
        original = _originals.get(func_name)
        if original is not None:
            setattr(uuid, func_name, original)

    # Restore extended functions (only if they were patched)
    for func_name in EXTENDED_UUID_FUNCS:
        if func_name in _originals:
            if hasattr(uuid, func_name):
                # Python 3.14+ - restore stdlib
                setattr(uuid, func_name, _originals[func_name])
            else:
                # Python < 3.14 - restore uuid6 module
                try:
                    import uuid6 as uuid6_module

                    setattr(uuid6_module, func_name, _originals[func_name])
                except ImportError:
                    pass

    _originals.clear()
    _proxy_installed = False

    # Clear all generator stacks
    with _generator_lock:
        for stack in _generator_stacks.values():
            stack.clear()


def is_proxy_installed() -> bool:
    """Check if the proxy is currently installed."""
    return _proxy_installed


def get_original(func_name: str = "uuid4") -> UUIDGenerator:
    """Get the original UUID function.

    This is used by generators that need to call the real function
    (e.g., RandomUUIDGenerator, or when a module is in the ignore list).

    Args:
        func_name: The UUID function name (default: "uuid4").

    Returns:
        The original UUID function.

    Raises:
        RuntimeError: If proxy is not installed.
        ValueError: If the function name is not supported.
    """
    if func_name not in UUID_FUNC_NAMES:
        raise ValueError(
            f"Unknown UUID function: {func_name}. "
            f"Supported: {', '.join(UUID_FUNC_NAMES)}"
        )

    original = _originals.get(func_name)
    if original is None:
        if func_name in EXTENDED_UUID_FUNCS:
            raise RuntimeError(
                f"{func_name} requires Python 3.14+ or the 'uuid6' package. "
                f"Install with: pip install uuid6"
            )
        raise RuntimeError(
            "Proxy not installed. Call install_proxy() first, "
            "or ensure pytest-uuid plugin is loaded."
        )
    return original


# Backward compatibility alias
def get_original_uuid4() -> Callable[[], uuid.UUID]:
    """Get the original uuid.uuid4 function.

    This is used by generators that need to call the real uuid4
    (e.g., RandomUUIDGenerator, or when a module is in the ignore list).

    Raises:
        RuntimeError: If proxy is not installed.
    """
    return get_original("uuid4")


class GeneratorToken:
    """Token returned by set_generator() for proper stack management."""

    def __init__(self, generator: UUIDGenerator, func_name: str = "uuid4") -> None:
        self.generator = generator
        self.func_name = func_name


def set_generator(
    generator: UUIDGenerator,
    func_name: str = "uuid4",
) -> GeneratorToken:
    """Set the current UUID generator for this context.

    Args:
        generator: A callable that returns UUIDs (typically a patched function
            with call tracking and generator logic).
        func_name: The UUID function name to set the generator for.
            Default is "uuid4" for backward compatibility.

    Returns:
        A token that can be used to reset the generator later.
        Pass this token to reset_generator() in __exit__.

    Raises:
        ValueError: If the function name is not supported.
    """
    if func_name not in UUID_FUNC_NAMES:
        raise ValueError(
            f"Unknown UUID function: {func_name}. "
            f"Supported: {', '.join(UUID_FUNC_NAMES)}"
        )

    with _generator_lock:
        _generator_stacks[func_name].append(generator)
    return GeneratorToken(generator, func_name)


def reset_generator(token: GeneratorToken) -> None:
    """Reset the generator to its previous value.

    Args:
        token: The token returned by set_generator().
            This removes the generator from the stack.
    """
    with _generator_lock:
        stack = _generator_stacks.get(token.func_name)
        if stack is None:
            return
        # Remove the generator from the stack
        # Should be at the end if contexts are properly nested
        if stack and stack[-1] is token.generator:
            stack.pop()
        elif token.generator in stack:
            # Handle out-of-order cleanup (shouldn't happen normally)
            stack.remove(token.generator)


def get_current_generator(func_name: str = "uuid4") -> UUIDGenerator | None:
    """Get the current generator for a UUID function, if any.

    Args:
        func_name: The UUID function name (default: "uuid4").

    Returns:
        The current generator callable, or None if outside any freeze context.
    """
    with _generator_lock:
        stack = _generator_stacks.get(func_name)
        return stack[-1] if stack else None
