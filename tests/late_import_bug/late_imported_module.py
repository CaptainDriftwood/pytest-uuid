"""Module that uses `from uuid import uuid4` - will not be patched when imported late.

This module demonstrates the bug where direct imports of uuid4 are not patched
when the module is imported AFTER freeze_uuid.__enter__() has run.

The problem: When Python executes `from uuid import uuid4`, it creates a
reference to the uuid4 function AT IMPORT TIME. If freeze_uuid hasn't patched
uuid.uuid4 yet, this module gets the ORIGINAL function. If freeze_uuid has
already patched it but this module is imported later, it gets the PATCHED
version - but only in sys.modules, not in THIS module's namespace.

The key insight: `from uuid import uuid4` creates a NAME BINDING in this
module's namespace. Once created, it doesn't change when uuid.uuid4 is
patched later.
"""

from uuid import uuid4  # Direct import - creates snapshot reference


def generate_uuid():
    """Generate a UUID using the direct import.

    This function will return NON-DETERMINISTIC UUIDs when this module
    is imported after freeze_uuid starts, because the `uuid4` reference
    points to the original (unpatched) function.
    """
    return uuid4()


def get_correlation_id():
    """Simulate a real-world use case: generating correlation IDs.

    In production code, this pattern is common:
    - Module imported at runtime (e.g., in Lambda handler)
    - Uses `from uuid import uuid4` for convenience
    - Generates UUIDs for tracing/logging

    This breaks deterministic testing because the UUIDs are random.
    """
    return str(uuid4())