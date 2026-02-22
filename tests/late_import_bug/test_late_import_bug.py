"""Test verifying that late imports work correctly with the proxy approach.

With the proxy-based patching (introduced to fix Bug #31 and the Pydantic
default_factory issue), modules can be imported at any time and will still
work correctly because:

1. uuid.uuid4 is permanently replaced with a proxy at plugin load
2. Any code that captures uuid4 (via `from uuid import uuid4`) gets the proxy
3. The proxy delegates to the current context's generator at call time

This eliminates the need for:
- Import hook interception
- Module-level patching/restoration
- Stale patch detection
"""

import sys
import uuid

from pytest_uuid import freeze_uuid


def _cleanup_module_properly():
    """Clean up the module from sys.modules AND parent package attribute.

    This forces a true fresh import on next import statement.
    """
    module_name = "tests.late_import_bug.late_imported_module"
    if module_name in sys.modules:
        del sys.modules[module_name]
    # Also remove from parent package to force real reimport
    import tests.late_import_bug

    if hasattr(tests.late_import_bug, "late_imported_module"):
        delattr(tests.late_import_bug, "late_imported_module")


class TestProxyBasedPatching:
    """Tests verifying the proxy approach works for all import scenarios."""

    def test_direct_uuid4_is_mocked(self, freeze_uuids_for_test):
        """Calling uuid.uuid4() directly is mocked and deterministic."""
        freeze_uuids_for_test.reset()
        uuid1 = uuid.uuid4()

        freeze_uuids_for_test.reset()
        uuid1_again = uuid.uuid4()

        assert uuid1 == uuid1_again, "Direct uuid.uuid4() should be deterministic"

    def test_early_imported_module_is_mocked(self, freeze_uuids_for_test):
        """Module with `from uuid import uuid4` is mocked via proxy."""
        from tests.late_import_bug import late_imported_module

        freeze_uuids_for_test.reset()
        uuid1 = late_imported_module.generate_uuid()

        freeze_uuids_for_test.reset()
        uuid1_again = late_imported_module.generate_uuid()

        assert uuid1 == uuid1_again, "Module should be deterministic via proxy"

    def test_late_import_during_context_works(self):
        """Module imported during freeze_uuid context works via proxy."""
        _cleanup_module_properly()

        with freeze_uuid(seed=42) as freezer:
            # Import DURING context - gets the proxy
            from tests.late_import_bug import late_imported_module

            freezer.reset()
            uuid1 = late_imported_module.generate_uuid()

            freezer.reset()
            uuid1_again = late_imported_module.generate_uuid()

            assert uuid1 == uuid1_again, "Late import should work via proxy"

    def test_module_works_across_contexts(self):
        """Module continues to work correctly across multiple freeze_uuid contexts."""
        _cleanup_module_properly()

        # First context
        with freeze_uuid(seed=42) as freezer_a:
            from tests.late_import_bug import late_imported_module

            freezer_a.reset()
            uuid_from_a = late_imported_module.generate_uuid()

        # Second context with different seed
        with freeze_uuid(seed=99) as freezer_b:
            freezer_b.reset()
            uuid_from_b = late_imported_module.generate_uuid()

            # Should be deterministic within context B
            freezer_b.reset()
            uuid_from_b_again = late_imported_module.generate_uuid()
            assert uuid_from_b == uuid_from_b_again

        # Different seeds should produce different UUIDs
        assert uuid_from_a != uuid_from_b

    def test_correlation_id_is_deterministic(self, freeze_uuids_for_test):
        """Correlation IDs are deterministic because module uses proxy."""
        from tests.late_import_bug import late_imported_module

        freeze_uuids_for_test.reset()
        id1 = late_imported_module.get_correlation_id()

        freeze_uuids_for_test.reset()
        id2 = late_imported_module.get_correlation_id()

        assert id1 == id2, "Correlation IDs should be deterministic"

    def test_outside_context_returns_random_uuids(self):
        """Outside any freeze_uuid context, returns random UUIDs."""
        _cleanup_module_properly()

        # First, verify the proxy is installed (uuid.uuid4 should be the proxy)
        # Import module outside of any context
        from tests.late_import_bug import late_imported_module

        # Generate some UUIDs outside context
        uuid1 = late_imported_module.generate_uuid()
        uuid2 = late_imported_module.generate_uuid()

        # They should be different (random)
        assert uuid1 != uuid2, "Outside context should return random UUIDs"
        # They should be valid UUIDs
        assert isinstance(uuid1, uuid.UUID)
        assert isinstance(uuid2, uuid.UUID)
