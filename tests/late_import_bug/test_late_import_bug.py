"""Test demonstrating import patching edge case in pytest-uuid (Bug #2).

This test demonstrates an edge case where modules with `from uuid import uuid4`
are not properly patched by _find_uuid4_imports() when the module's uuid4
attribute is not the original uuid.uuid4 function.

THE BUG SCENARIO:
=================

When tests manipulate sys.modules (common in test isolation), the following
sequence can cause non-deterministic UUID generation:

1. Test A runs with freeze_uuid context
2. A module is imported (or reimported) during Test A
3. The module's `from uuid import uuid4` gets the PATCHED uuid4 from Test A
4. Test A ends, freeze_uuid.__exit__ runs
5. __exit__ restores uuid.uuid4 to original
6. BUT the module's uuid4 still points to Test A's patched function
   (module wasn't in _patched_locations because it was imported AFTER __enter__)

7. Test B runs with new freeze_uuid context
8. _find_uuid4_imports(original_uuid4) scans sys.modules
9. Finds the module, checks: module.uuid4 is original_uuid4?
10. module.uuid4 = Test A's stale patched function (NOT original_uuid4)
11. _find_uuid4_imports skips this module - doesn't add to patch list!

12. Test B uses the module
13. module.uuid4() calls the STALE patched function from Test A
14. Test A's generator is no longer valid, returns random UUIDs
15. UUIDs are non-deterministic

ROOT CAUSE:
===========

_find_uuid4_imports() uses identity comparison (module.uuid4 is original_uuid4)
to find modules to patch. If a module's uuid4 is NOT the original function
(e.g., it's a patched function from a previous test that wasn't restored),
the module won't be found and won't be patched.

WHEN THIS HAPPENS:
==================

1. Test isolation that removes modules from sys.modules and reimports them
2. Dynamic imports during freeze_uuid context
3. Modules imported in fixtures or helper functions during test execution

WORKAROUND:
===========

Ensure modules with `from uuid import uuid4` are imported BEFORE freeze_uuid
starts (e.g., at module level in test files), not during test execution.
"""

import sys
import uuid

import pytest

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


def _restore_module_to_original_state():
    """Restore the module's uuid4 to the original function.

    This ensures tests don't interfere with each other.
    """
    module_name = "tests.late_import_bug.late_imported_module"
    if module_name in sys.modules:
        module = sys.modules[module_name]
        # Restore uuid4 to the original function from the uuid module
        import uuid as uuid_module

        module.uuid4 = uuid_module.uuid4


@pytest.fixture(autouse=True)
def cleanup_module_state():
    """Cleanup module state before and after each test."""
    _restore_module_to_original_state()
    yield
    _restore_module_to_original_state()


class TestNormalBehavior:
    """Tests verifying that normal import scenarios work correctly.

    These tests pass because the module's uuid4 is restored to the original
    function before each test, so _find_uuid4_imports() correctly finds and
    patches it.
    """

    def test_direct_uuid4_is_patched(self, freeze_uuids_for_test):
        """Calling uuid.uuid4() directly is patched and deterministic."""
        freeze_uuids_for_test.reset()
        uuid1 = uuid.uuid4()

        freeze_uuids_for_test.reset()
        uuid1_again = uuid.uuid4()

        assert uuid1 == uuid1_again, "Direct uuid.uuid4() should be deterministic"

    def test_early_imported_module_is_patched(self, freeze_uuids_for_test):
        """Module with `from uuid import uuid4` IS patched when uuid4 is original.

        This works because the cleanup fixture restores module.uuid4 to the
        original uuid.uuid4 function before each test, so _find_uuid4_imports()
        finds it.
        """
        # Import the module (it should be in sys.modules with original uuid4)
        from tests.late_import_bug import late_imported_module

        freeze_uuids_for_test.reset()
        uuid1 = late_imported_module.generate_uuid()

        freeze_uuids_for_test.reset()
        uuid1_again = late_imported_module.generate_uuid()

        assert uuid1 == uuid1_again, (
            "Module with original uuid4 should be deterministic - "
            "_find_uuid4_imports correctly patches it"
        )

    def test_module_uuid4_is_patched(self, freeze_uuids_for_test):
        """Verify that the module's uuid4 attribute IS the patched function."""
        from tests.late_import_bug import late_imported_module

        module_uuid4 = late_imported_module.uuid4
        original_uuid4_fn = freeze_uuids_for_test._original_uuid4

        assert module_uuid4 is not original_uuid4_fn, (
            "Module's uuid4 should be patched, not original"
        )

    def test_correlation_id_is_deterministic(self, freeze_uuids_for_test):
        """Correlation IDs are deterministic because module is patched."""
        from tests.late_import_bug import late_imported_module

        freeze_uuids_for_test.reset()
        id1 = late_imported_module.get_correlation_id()

        freeze_uuids_for_test.reset()
        id2 = late_imported_module.get_correlation_id()

        assert id1 == id2, "Correlation IDs should be deterministic"


class TestBugDemonstration:
    """Tests verifying Bug #31 is FIXED.

    GitHub Issue: https://github.com/CaptainDriftwood/pytest-uuid/issues/31

    These tests verify the fix works when:
    1. One freeze_uuid context patches a module during import
    2. That context exits (module's uuid4 is now properly restored)
    3. A NEW freeze_uuid context starts and correctly patches the module
    """

    def test_late_import_is_properly_tracked_and_restored(self):
        """FIXED: Module imported during context is tracked and restored on exit.

        The import hook now:
        1. Catches modules imported during freeze_uuid context
        2. Tracks them in _patched_locations
        3. Restores their uuid4 to original on __exit__
        """
        _cleanup_module_properly()

        # --- Context A ---
        with freeze_uuid(seed=42) as freezer_a:
            # Import during context - module gets PATCHED uuid4
            from tests.late_import_bug import late_imported_module

            # Verify it's working in this context
            freezer_a.reset()
            uuid_in_context_a = late_imported_module.generate_uuid()
            freezer_a.reset()
            uuid_in_context_a_again = late_imported_module.generate_uuid()
            assert uuid_in_context_a == uuid_in_context_a_again, (
                "Should work within same context"
            )

        # --- After Context A ends ---
        # FIXED: Module's uuid4 is now restored to original
        # (import hook tracked the module and restored it on __exit__)
        assert late_imported_module.uuid4 is uuid.uuid4, (
            "Module's uuid4 should be restored to original after __exit__"
        )

        # --- Context B ---
        with freeze_uuid(seed=99) as freezer_b:
            # FIXED: Module is now properly found and patched
            original_uuid4 = freezer_b._original_uuid4

            # Module's uuid4 is patched (not the original)
            assert late_imported_module.uuid4 is not original_uuid4, (
                "Module's uuid4 should be patched by new context"
            )

            # FIXED: UUIDs are now deterministic!
            freezer_b.reset()
            uuid_in_context_b_1 = late_imported_module.generate_uuid()
            freezer_b.reset()
            uuid_in_context_b_2 = late_imported_module.generate_uuid()

            assert uuid_in_context_b_1 == uuid_in_context_b_2, (
                "UUIDs should be deterministic after fix"
            )


class TestWorkaround:
    """Tests demonstrating the workaround: proper cleanup forces fresh import."""

    def test_proper_cleanup_enables_patching(self, freeze_uuids_for_test):
        """Workaround: Cleaning both sys.modules AND parent package attribute.

        When we properly clean up the module (from sys.modules AND the parent
        package's attribute), the next import truly reimports the module.
        Since uuid.uuid4 is patched at that point, the module's uuid4 gets
        the patched function.
        """
        _cleanup_module_properly()

        from tests.late_import_bug import late_imported_module

        freeze_uuids_for_test.reset()
        uuid1 = late_imported_module.generate_uuid()

        freeze_uuids_for_test.reset()
        uuid1_again = late_imported_module.generate_uuid()

        assert uuid1 == uuid1_again, (
            "With proper cleanup, fresh import gets patched uuid4"
        )

    def test_proper_cleanup_uuid4_is_patched(self, freeze_uuids_for_test):
        """Verify that proper cleanup results in patched uuid4."""
        _cleanup_module_properly()

        from tests.late_import_bug import late_imported_module

        module_uuid4 = late_imported_module.uuid4
        original_uuid4_fn = freeze_uuids_for_test._original_uuid4

        # With proper cleanup, module's uuid4 is the patched function
        assert module_uuid4 is not original_uuid4_fn, (
            "With proper cleanup, module's uuid4 is patched"
        )
