"""Compatibility layer for UUID functions across Python versions.

This module provides version-aware imports for uuid6, uuid7, and uuid8 functions:
- Python 3.14+: Uses stdlib uuid module
- Python 3.9-3.13: Uses uuid6 backport package

The uuid6 package is a conditional dependency (only installed on Python < 3.14).
"""

from __future__ import annotations

import sys
import uuid
from typing import TYPE_CHECKING, Callable

# Feature flags for conditional functionality
HAS_UUID6_7_8: bool
"""True if uuid6, uuid7, uuid8 functions are available (Python 3.14+ or uuid6 package)."""

# Type alias for UUID generator functions
UUIDFunc = Callable[..., uuid.UUID]

# Version-aware imports for uuid6/uuid7/uuid8
if sys.version_info >= (3, 14):
    # Python 3.14+ has native support
    from uuid import uuid6 as _uuid6
    from uuid import uuid7 as _uuid7
    from uuid import uuid8 as _uuid8

    HAS_UUID6_7_8 = True
else:
    # Python 3.9-3.13: use uuid6 backport package
    try:
        from uuid6 import uuid6 as _uuid6
        from uuid6 import uuid7 as _uuid7
        from uuid6 import uuid8 as _uuid8

        HAS_UUID6_7_8 = True
    except ImportError:
        # uuid6 package not installed - functions unavailable
        HAS_UUID6_7_8 = False
        _uuid6 = None  # type: ignore[assignment]
        _uuid7 = None  # type: ignore[assignment]
        _uuid8 = None  # type: ignore[assignment]


# Export the functions (may be None if not available)
uuid6: UUIDFunc | None = _uuid6 if HAS_UUID6_7_8 else None
uuid7: UUIDFunc | None = _uuid7 if HAS_UUID6_7_8 else None
uuid8: UUIDFunc | None = _uuid8 if HAS_UUID6_7_8 else None


def require_uuid6_7_8(func_name: str) -> None:
    """Raise an error if uuid6/7/8 functions are not available.

    Args:
        func_name: The function name being requested (for error message).

    Raises:
        RuntimeError: If uuid6/7/8 are not available.
    """
    if not HAS_UUID6_7_8:
        raise RuntimeError(
            f"{func_name} mocking requires Python 3.14+ or the 'uuid6' package. "
            f"Install with: pip install uuid6"
        )


# For type checking, provide proper types regardless of runtime availability
if TYPE_CHECKING:
    # These are always available for type checking purposes
    uuid6: UUIDFunc  # type: ignore[no-redef]
    uuid7: UUIDFunc  # type: ignore[no-redef]
    uuid8: UUIDFunc  # type: ignore[no-redef]
