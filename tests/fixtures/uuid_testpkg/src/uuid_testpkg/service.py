"""Service module using 'from uuid import uuid4' pattern.

This is the pattern that creates a module-level reference to uuid4,
which requires pytest-uuid to discover and patch via _find_uuid4_imports().
"""

from uuid import uuid4


def generate_id():
    """Generate a UUID using direct import."""
    return uuid4()


class UUIDService:
    """Service class that generates UUIDs."""

    def __init__(self, prefix="id"):
        self.prefix = prefix

    def create_id(self):
        """Create a new UUID."""
        return uuid4()

    def create_prefixed_id(self):
        """Create a prefixed UUID string."""
        return f"{self.prefix}-{uuid4()}"

    def create_record(self, name):
        """Create a record with auto-generated UUID."""
        return {
            "id": str(uuid4()),
            "name": name,
        }
