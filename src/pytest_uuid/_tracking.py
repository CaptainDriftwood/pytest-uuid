"""Call tracking mixin and utilities for UUID generation tracking.

This module provides shared functionality for tracking uuid4() calls
across UUIDMocker, UUIDSpy, and UUIDFreezer classes.
"""

from __future__ import annotations

import hashlib
import inspect
import sys
import uuid

from pytest_uuid.types import UUIDCall


def _get_node_seed(node_id: str) -> int:
    """Generate a deterministic seed from a test node ID.

    Args:
        node_id: The pytest node ID (e.g., "tests/test_foo.py::TestClass::test_method")

    Returns:
        A deterministic integer seed derived from the node ID.
    """
    return int(hashlib.md5(node_id.encode()).hexdigest()[:8], 16)  # noqa: S324


def _get_caller_info(skip_frames: int = 2) -> tuple[str | None, str | None]:
    """Get caller module and file information.

    Args:
        skip_frames: Number of frames to skip (default 2 skips this function
                    and the calling function).

    Returns:
        Tuple of (module_name, file_path) or (None, None) if unavailable.
    """
    frame = inspect.currentframe()
    try:
        # Skip the specified number of frames
        for _ in range(skip_frames):
            if frame is not None:
                frame = frame.f_back

        if frame is None:
            return None, None

        module_name = frame.f_globals.get("__name__")
        file_path = frame.f_code.co_filename
        return module_name, file_path
    finally:
        del frame


def _find_uuid4_imports(original_uuid4: object) -> list[tuple[object, str]]:
    """Find all modules that have imported uuid4 directly.

    Returns a list of (module, attribute_name) tuples for modules that have
    the original uuid4 function as an attribute. This handles both standard
    imports (from uuid import uuid4) and aliased imports
    (from uuid import uuid4 as my_uuid).
    """
    imports = []
    for module in sys.modules.values():
        if module is None:
            continue
        try:
            module_dict = getattr(module, "__dict__", None)
            if module_dict is None:
                continue
            # Scan all attributes to find any that reference the original uuid4.
            # This handles aliased imports like: from uuid import uuid4 as my_uuid
            for attr_name, attr_value in module_dict.items():
                if attr_value is original_uuid4:
                    imports.append((module, attr_name))
        except (TypeError, AttributeError, RuntimeError):
            # TypeError: unusual module types
            # AttributeError: module attributes inaccessible during teardown
            # RuntimeError: various edge cases with unusual modules
            continue
    return imports


class CallTrackingMixin:
    """Mixin class providing call tracking functionality.

    Classes using this mixin must initialize the tracking attributes
    in their __init__:
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

    Note:
        This class is NOT thread-safe. The tracking methods modify shared
        state without synchronization. This is acceptable for typical pytest
        usage where tests run sequentially, but concurrent uuid4() calls
        from multiple threads may result in race conditions. If thread-safe
        tracking is needed, consider using threading.Lock in your code.
    """

    _call_count: int
    _generated_uuids: list[uuid.UUID]
    _calls: list[UUIDCall]

    def _record_call(
        self,
        result: uuid.UUID,
        was_mocked: bool,
        caller_module: str | None,
        caller_file: str | None,
    ) -> None:
        """Record a uuid4 call for tracking.

        Args:
            result: The UUID that was generated.
            was_mocked: True if the UUID was mocked, False if real.
            caller_module: The module name where the call originated.
            caller_file: The file path where the call originated.
        """
        self._call_count += 1
        self._generated_uuids.append(result)
        self._calls.append(
            UUIDCall(
                uuid=result,
                was_mocked=was_mocked,
                caller_module=caller_module,
                caller_file=caller_file,
            )
        )

    def _reset_tracking(self) -> None:
        """Reset all tracking data to initial state."""
        self._call_count = 0
        self._generated_uuids.clear()
        self._calls.clear()

    @property
    def call_count(self) -> int:
        """Get the number of times uuid4 was called."""
        return self._call_count

    @property
    def generated_uuids(self) -> list[uuid.UUID]:
        """Get a list of all UUIDs that have been generated.

        Returns a copy to prevent external modification.
        """
        return list(self._generated_uuids)

    @property
    def last_uuid(self) -> uuid.UUID | None:
        """Get the most recently generated UUID, or None if none generated."""
        return self._generated_uuids[-1] if self._generated_uuids else None

    @property
    def calls(self) -> list[UUIDCall]:
        """Get detailed metadata for all uuid4 calls.

        Returns a copy to prevent external modification.
        """
        return list(self._calls)

    @property
    def mocked_calls(self) -> list[UUIDCall]:
        """Get only the calls that returned mocked UUIDs."""
        return [c for c in self._calls if c.was_mocked]

    @property
    def real_calls(self) -> list[UUIDCall]:
        """Get only the calls that returned real UUIDs (e.g., spy mode)."""
        return [c for c in self._calls if not c.was_mocked]

    @property
    def mocked_count(self) -> int:
        """Get the number of calls that returned mocked UUIDs."""
        return sum(1 for c in self._calls if c.was_mocked)

    @property
    def real_count(self) -> int:
        """Get the number of calls that returned real UUIDs."""
        return sum(1 for c in self._calls if not c.was_mocked)

    def calls_from(self, module_prefix: str) -> list[UUIDCall]:
        """Get calls from modules matching the given prefix.

        Args:
            module_prefix: Module name prefix to filter by (e.g., "myapp.models").

        Returns:
            List of UUIDCall records from matching modules.
        """
        return [
            c
            for c in self._calls
            if c.caller_module and c.caller_module.startswith(module_prefix)
        ]
