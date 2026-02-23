"""Permanent proxy for uuid.uuid4() that enables context-aware mocking.

This module implements a proxy-based patching approach that solves several
edge cases with the traditional attribute-patching approach:

1. Pydantic default_factory=uuid4 - captures function at class definition
2. Late imports during freeze_uuid context - stale patched functions
3. Closures and data structures storing uuid4 references

Architecture:
    1. At plugin load (pytest_configure), install _proxy_uuid4 as uuid.uuid4
    2. Any code that imports uuid4 (before or after) gets the proxy
    3. The proxy checks a thread-safe stack for the current generator
    4. If a generator is set, use it; otherwise, call original uuid4

Thread Safety:
    Uses a thread-safe global stack protected by a lock. This ensures:
    - All threads see the same active generator (unlike ContextVar)
    - Nested contexts work correctly (stack-based)
    - Thread-safe access to the generator stack

Usage:
    # At plugin initialization (once)
    install_proxy()

    # In freeze_uuid.__enter__
    token = set_generator(my_patched_uuid4)

    # In freeze_uuid.__exit__
    reset_generator(token)
"""

from __future__ import annotations

import threading
import uuid
from typing import Callable

# The original uuid.uuid4 function, captured before any patching
_original_uuid4: Callable[[], uuid.UUID] | None = None

# Thread-safe stack of generators, protected by a lock
# Each freeze_uuid context pushes a generator onto the stack
# Nested contexts result in multiple entries; innermost is at the end
_generator_stack: list[Callable[[], uuid.UUID]] = []
_generator_lock = threading.Lock()

# Track whether the proxy has been installed
_proxy_installed: bool = False


def _proxy_uuid4() -> uuid.UUID:
    """Permanent proxy that delegates to current generator.

    This function replaces uuid.uuid4 at plugin initialization.
    It checks the generator stack:
    - If a generator is set (inside a freeze_uuid context), call it
    - If not set (outside any context), call the original uuid4
    """
    generator = None
    with _generator_lock:
        if _generator_stack:
            generator = _generator_stack[-1]
    if generator is not None:
        # Call outside lock to avoid holding lock during user code
        return generator()
    # Fall back to original uuid4
    assert _original_uuid4 is not None, "Proxy called before installation"
    return _original_uuid4()


def install_proxy() -> None:
    """Install the uuid4 proxy.

    This should be called once at plugin initialization (pytest_configure).
    It replaces uuid.uuid4 with our proxy function.

    The proxy is idempotent - calling multiple times is safe.
    """
    global _original_uuid4, _proxy_installed

    if _proxy_installed:
        return

    # Capture the original uuid4 before any patching
    _original_uuid4 = uuid.uuid4

    # Install our proxy
    uuid.uuid4 = _proxy_uuid4  # type: ignore[assignment]

    _proxy_installed = True


def uninstall_proxy() -> None:
    """Restore the original uuid.uuid4.

    This is primarily for testing the proxy itself.
    In normal usage, the proxy stays installed for the pytest session.
    """
    global _original_uuid4, _proxy_installed

    if not _proxy_installed:
        return

    if _original_uuid4 is not None:
        uuid.uuid4 = _original_uuid4  # type: ignore[assignment]

    _original_uuid4 = None
    _proxy_installed = False

    # Clear the generator stack
    with _generator_lock:
        _generator_stack.clear()


def is_proxy_installed() -> bool:
    """Check if the proxy is currently installed."""
    return _proxy_installed


def get_original_uuid4() -> Callable[[], uuid.UUID]:
    """Get the original uuid.uuid4 function.

    This is used by generators that need to call the real uuid4
    (e.g., RandomUUIDGenerator, or when a module is in the ignore list).

    Raises:
        RuntimeError: If proxy is not installed.
    """
    if _original_uuid4 is None:
        raise RuntimeError(
            "Proxy not installed. Call install_proxy() first, "
            "or ensure pytest-uuid plugin is loaded."
        )
    return _original_uuid4


class GeneratorToken:
    """Token returned by set_generator() for proper stack management."""

    def __init__(self, generator: Callable[[], uuid.UUID]) -> None:
        self.generator = generator


def set_generator(
    generator: Callable[[], uuid.UUID],
) -> GeneratorToken:
    """Set the current UUID generator for this context.

    Args:
        generator: A callable that returns UUIDs (typically a patched uuid4
            function with call tracking and generator logic).

    Returns:
        A token that can be used to reset the generator later.
        Pass this token to reset_generator() in __exit__.
    """
    with _generator_lock:
        _generator_stack.append(generator)
    return GeneratorToken(generator)


def reset_generator(token: GeneratorToken) -> None:
    """Reset the generator to its previous value.

    Args:
        token: The token returned by set_generator().
            This removes the generator from the stack.
    """
    with _generator_lock:
        # Remove the generator from the stack
        # Should be at the end if contexts are properly nested
        if _generator_stack and _generator_stack[-1] is token.generator:
            _generator_stack.pop()
        elif token.generator in _generator_stack:
            # Handle out-of-order cleanup (shouldn't happen normally)
            _generator_stack.remove(token.generator)


def get_current_generator() -> Callable[[], uuid.UUID] | None:
    """Get the current generator, if any.

    Returns:
        The current generator callable, or None if outside any freeze context.
    """
    with _generator_lock:
        return _generator_stack[-1] if _generator_stack else None
