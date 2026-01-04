"""Test fixture package that uses uuid.uuid4() in various patterns.

This package is used to test pytest-uuid's ability to mock uuid.uuid4()
calls in truly installed packages (site-packages).
"""

from uuid_testpkg.alt_service import AltUUIDService, alt_generate_id
from uuid_testpkg.service import UUIDService, generate_id

__all__ = [
    "UUIDService",
    "generate_id",
    "AltUUIDService",
    "alt_generate_id",
]
