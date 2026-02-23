"""Call tracking mixin and utilities for UUID generation tracking.

This module provides shared functionality for tracking uuid4() calls
across UUIDMocker, UUIDSpy, and UUIDFreezer classes.
"""

from __future__ import annotations

import gc
import hashlib
import inspect
import sys
import uuid
from types import FrameType, FunctionType

from pytest_uuid.types import UUIDCall


def _get_node_seed(node_id: str) -> int:
    """Generate a deterministic seed from a test node ID.

    Args:
        node_id: The pytest node ID (e.g., "tests/test_foo.py::TestClass::test_method")

    Returns:
        A deterministic integer seed derived from the node ID.
    """
    return int(hashlib.md5(node_id.encode()).hexdigest()[:8], 16)  # noqa: S324


def _get_qualname(frame: FrameType) -> str | None:
    """Get qualified name of the function from a frame.

    On Python 3.11+, uses the native co_qualname attribute which provides
    accurate qualified names in all cases.

    On Python 3.9/3.10, uses best-effort reconstruction via:
    1. Instance method detection (self parameter) -> type(self).__qualname__.method
    2. Class method detection (cls parameter) -> cls.__qualname__.method
    3. gc.get_referrers() to find the function object when unambiguous
    4. Fallback to simple function name

    Note: The fallback approach has semantic differences in some edge cases:
    - Inherited methods: Returns Child.method instead of Parent.method
    - Multiple closures sharing code: Returns simple name when ambiguous

    Args:
        frame: The frame object to extract qualified name from.

    Returns:
        Qualified name like "MyClass.method" or "outer.<locals>.inner",
        or the simple function name if reconstruction fails, or None.
    """
    # Python 3.11+: use native co_qualname
    # TODO: When minimum Python version is 3.11+, simplify to just:
    #       return frame.f_code.co_qualname
    if sys.version_info >= (3, 11):
        return frame.f_code.co_qualname

    func_name = frame.f_code.co_name

    # Approach 1: Instance method (check for 'self')
    self_obj = frame.f_locals.get("self")
    if self_obj is not None:
        return f"{type(self_obj).__qualname__}.{func_name}"

    # Approach 2: Class method (check for 'cls')
    cls_obj = frame.f_locals.get("cls")
    if cls_obj is not None and isinstance(cls_obj, type):
        return f"{cls_obj.__qualname__}.{func_name}"

    # Approach 3: Use gc.get_referrers() to find function object
    code = frame.f_code
    try:
        funcs = [f for f in gc.get_referrers(code) if isinstance(f, FunctionType)]
        if len(funcs) == 1:
            return funcs[0].__qualname__
        if len(funcs) > 1:
            # Try to disambiguate by matching __name__
            matching = [f for f in funcs if f.__name__ == func_name]
            if len(matching) == 1:
                return matching[0].__qualname__
    except Exception:  # noqa: S110
        # gc.get_referrers can fail in edge cases; fall back to simple name
        pass

    # Fallback to simple name
    return func_name


def _get_caller_info(
    skip_frames: int = 2,
) -> tuple[str | None, str | None, int | None, str | None, str | None]:
    """Get caller module, file, line number, function name, and qualname.

    Args:
        skip_frames: Number of frames to skip (default 2 skips this function
                    and the calling function).

    Returns:
        Tuple of (module_name, file_path, line_number, function_name, qualname).
        Any or all values may be None if unavailable.
    """
    frame = inspect.currentframe()
    try:
        # Skip the specified number of frames
        for _ in range(skip_frames):
            if frame is not None:
                frame = frame.f_back

        if frame is None:
            return None, None, None, None, None

        module_name = frame.f_globals.get("__name__")
        file_path = frame.f_code.co_filename
        line_number = frame.f_lineno
        function_name = frame.f_code.co_name
        qualname = _get_qualname(frame)
        return module_name, file_path, line_number, function_name, qualname
    finally:
        del frame


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
        caller_line: int | None = None,
        caller_function: str | None = None,
        caller_qualname: str | None = None,
    ) -> None:
        """Record a uuid4 call for tracking.

        Args:
            result: The UUID that was generated.
            was_mocked: True if the UUID was mocked, False if real.
            caller_module: The module name where the call originated.
            caller_file: The file path where the call originated.
            caller_line: The line number where the call originated.
            caller_function: The function name where the call originated.
            caller_qualname: The qualified name of the function (e.g., "MyClass.method").
        """
        self._call_count += 1
        self._generated_uuids.append(result)
        self._calls.append(
            UUIDCall(
                uuid=result,
                was_mocked=was_mocked,
                caller_module=caller_module,
                caller_file=caller_file,
                caller_line=caller_line,
                caller_function=caller_function,
                caller_qualname=caller_qualname,
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
