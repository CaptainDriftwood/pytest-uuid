"""Import hook for patching uuid4 in dynamically imported modules.

This module provides an import hook that intercepts module imports during a
freeze_uuid context. This ensures that modules imported AFTER __enter__:

1. Get their uuid4 references patched (handles `from uuid import uuid4 as uid4`)
2. Are tracked in _patched_locations for proper restoration on __exit__

The hook handles all import patterns:
- `from uuid import uuid4` → module.uuid4 is patched
- `from uuid import uuid4 as uid4` → module.uid4 is patched
- `import uuid as my_uuid` → already works (reference to uuid module)

This approach is inspired by freezegun and time-machine which use similar
import hooking to ensure comprehensive patching.
"""

from __future__ import annotations

import builtins
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    import uuid


# Marker attribute to identify patched uuid4 functions
PATCHED_MARKER = "_pytest_uuid_patched"


def is_patched_uuid4(func: object) -> bool:
    """Check if a function is a patched uuid4 from pytest-uuid.

    We use `is True` to ensure we only match functions explicitly marked
    by pytest-uuid, not mock objects or other special callables that might
    return truthy values for attribute access.
    """
    return callable(func) and getattr(func, PATCHED_MARKER, None) is True


def mark_as_patched(func: Callable[[], uuid.UUID]) -> Callable[[], uuid.UUID]:
    """Mark a function as a patched uuid4."""
    setattr(func, PATCHED_MARKER, True)
    return func


class UUIDImportHook:
    """Import hook that patches uuid4 in newly imported modules.

    This hook wraps builtins.__import__ to intercept all imports during
    a freeze_uuid context. When a new module is imported, it scans for
    uuid4 references and patches them.

    Usage:
        hook = UUIDImportHook(original_uuid4, patched_uuid4, patched_locations)
        hook.install()
        try:
            # imports during this block are intercepted
            ...
        finally:
            hook.uninstall()
    """

    def __init__(
        self,
        original_uuid4: Callable[[], uuid.UUID],
        patched_uuid4: Callable[[], uuid.UUID],
        patched_locations: list[tuple[object, str, object]],
    ) -> None:
        """Initialize the import hook.

        Args:
            original_uuid4: The original uuid.uuid4 function.
            patched_uuid4: The patched uuid4 function to use.
            patched_locations: Shared list to track patched locations for restoration.
                This is the same list used by UUIDFreezer._patched_locations.
        """
        self.original_uuid4 = original_uuid4
        self.patched_uuid4 = patched_uuid4
        self.patched_locations = patched_locations
        self._original_import: Callable[..., Any] | None = None
        self._installed = False

    def install(self) -> None:
        """Install the import hook."""
        if self._installed:
            return

        self._original_import = builtins.__import__

        # Create closure over self for the patching import function
        original_import = self._original_import
        hook = self

        def patching_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: Sequence[str] = (),
            level: int = 0,
        ) -> Any:
            # Track modules before import
            modules_before = set(sys.modules.keys())

            # Perform the actual import
            result = original_import(name, globals, locals, fromlist, level)

            # Find newly imported modules
            modules_after = set(sys.modules.keys())
            new_modules = modules_after - modules_before

            # Patch uuid4 in any new modules
            for module_name in new_modules:
                module = sys.modules.get(module_name)
                if module is not None:
                    hook._patch_module(module)

            return result

        builtins.__import__ = patching_import  # type: ignore[assignment]
        self._installed = True

    def uninstall(self) -> None:
        """Uninstall the import hook."""
        if not self._installed:
            return

        if self._original_import is not None:
            builtins.__import__ = self._original_import  # type: ignore[assignment]
            self._original_import = None

        self._installed = False

    def _patch_module(self, module: object) -> None:
        """Patch uuid4 references in a module.

        Finds any attribute that is:
        1. The original uuid4 function (by identity)
        2. A stale patched function from a previous context (by marker)
        3. The current patched function (just needs tracking)

        This handles aliased imports like `from uuid import uuid4 as uid4`.
        """
        try:
            module_dict = getattr(module, "__dict__", None)
            if module_dict is None:
                return

            # Iterate over a copy since we may modify during iteration
            for attr_name, attr_value in list(module_dict.items()):
                should_patch = False

                # Case 1: Has original uuid4 (imported before our context started)
                if attr_value is self.original_uuid4 or (
                    is_patched_uuid4(attr_value)
                    and attr_value is not self.patched_uuid4
                ):
                    should_patch = True

                # Case 3: Already has our patched function (just track it)
                elif attr_value is self.patched_uuid4:
                    # Already patched, but ensure it's tracked for restoration
                    if not self._is_tracked(module, attr_name):
                        self.patched_locations.append(
                            (module, attr_name, self.original_uuid4)
                        )
                    continue

                if should_patch:
                    setattr(module, attr_name, self.patched_uuid4)
                    if not self._is_tracked(module, attr_name):
                        self.patched_locations.append(
                            (module, attr_name, self.original_uuid4)
                        )

        except (TypeError, AttributeError, RuntimeError):
            # Skip problematic modules
            pass

    def _is_tracked(self, module: object, attr_name: str) -> bool:
        """Check if a module/attribute is already tracked for restoration."""
        return any(
            m is module and name == attr_name for m, name, _ in self.patched_locations
        )
