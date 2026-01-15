"""Alternative service module using 'import uuid' pattern.

This pattern accesses uuid4 via the module (uuid.uuid4()),
which is patched directly on the uuid module.
"""

import uuid


def alt_generate_id():
    """Generate a UUID using module import."""
    return uuid.uuid4()


class AltUUIDService:
    """Alternative service class using module import pattern."""

    def __init__(self, prefix="alt"):
        self.prefix = prefix

    def create_id(self):
        """Create a new UUID."""
        return uuid.uuid4()

    def create_prefixed_id(self):
        """Create a prefixed UUID string."""
        return f"{self.prefix}-{uuid.uuid4()}"
