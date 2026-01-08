"""Integration tests for Bug #31: Stale patched functions cause non-deterministic UUIDs.

GitHub Issue: https://github.com/CaptainDriftwood/pytest-uuid/issues/31

TODO: This bug will be fixed in a future release. Once fixed, the assertions
in these tests should be updated to expect DETERMINISTIC behavior:
- Change `assert uuid1 != uuid2` to `assert uuid1 == uuid2`
- Change `assert module_uuid4 is not original_uuid4` to `is original_uuid4`
- Change `assert "late_import_helper2" not in module_names` to `in`

This test reproduces the bug where modules imported DURING a freeze_uuid context
get a stale patched function that causes non-deterministic UUIDs in subsequent
freeze_uuid contexts.

The bug occurs because:
1. Module is imported DURING freeze_uuid context (after __enter__)
2. Module's `from uuid import uuid4` gets the patched function
3. Context exits, but module's uuid4 isn't in _patched_locations (not restored)
4. Next context's _find_uuid4_imports() doesn't find it (identity check fails)
5. Module's stale patched function returns random UUIDs

The existing tests don't catch this because they import helper modules at the
TOP of the test file (before any freeze_uuid context starts).
"""

from __future__ import annotations


def test_bug_stale_patch_causes_non_deterministic_uuids(pytester):
    """BUG #31: Module imported during freeze_uuid gets stale patched function.

    This test reproduces the bug by:
    1. Creating test_a that imports a module DURING freeze_uuid context
    2. Creating test_b that uses the same module with a different freeze_uuid
    3. Verifying that test_b gets NON-deterministic UUIDs (the bug)

    After the bug is fixed, this test should FAIL (UUIDs should be deterministic).
    """
    # Create helper module with `from uuid import uuid4`
    pytester.makepyfile(
        late_import_helper="""
from uuid import uuid4

def generate_uuid():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_stale_patch_bug="""
import sys
import pytest
from pytest_uuid import freeze_uuid

# NOTE: We do NOT import late_import_helper here!
# The bug requires importing it DURING a freeze_uuid context.

def test_a_import_during_freeze():
    '''Test A: Import module during freeze_uuid context.'''
    # Remove from cache to ensure fresh import
    if "late_import_helper" in sys.modules:
        del sys.modules["late_import_helper"]

    with freeze_uuid(seed=42) as freezer:
        # Import DURING freeze_uuid context - this is the bug trigger
        import late_import_helper

        # Verify it works in this context
        freezer.reset()
        uuid1 = late_import_helper.generate_uuid()
        freezer.reset()
        uuid1_again = late_import_helper.generate_uuid()
        assert uuid1 == uuid1_again, "Should work in same context"

def test_b_use_module_in_new_context():
    '''Test B: Use same module in new freeze_uuid context.'''
    # Module should still be in sys.modules from test_a
    import late_import_helper

    with freeze_uuid(seed=99) as freezer:
        # BUG: UUIDs are non-deterministic because module's uuid4
        # is a stale patched function from test_a's context
        freezer.reset()
        uuid1 = late_import_helper.generate_uuid()
        freezer.reset()
        uuid2 = late_import_helper.generate_uuid()

        # BUG DEMONSTRATION: These should be equal but ARE NOT
        # After bug is fixed, change this to: assert uuid1 == uuid2
        assert uuid1 != uuid2, (
            "BUG: UUIDs are non-deterministic. "
            "Stale patched function from test_a causes random UUIDs."
        )
"""
    )

    # Run tests in order (disable random ordering)
    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=2)


def test_bug_module_uuid4_is_stale_patched_function(pytester):
    """BUG #31: Verify module's uuid4 is stale patched function, not original.

    This test verifies the root cause: after test_a's freeze_uuid context exits,
    the module's uuid4 is still the patched function (not restored to original).
    """
    pytester.makepyfile(
        late_import_helper2="""
from uuid import uuid4

def generate_uuid():
    return uuid4()

def get_uuid4_function():
    return uuid4
"""
    )

    pytester.makepyfile(
        test_stale_function="""
import sys
import uuid
from pytest_uuid import freeze_uuid

def test_a_creates_stale_reference():
    '''Import module during freeze_uuid, creating stale reference.'''
    if "late_import_helper2" in sys.modules:
        del sys.modules["late_import_helper2"]

    with freeze_uuid(seed=42):
        import late_import_helper2
        # Module's uuid4 is now the patched function

    # After __exit__, uuid.uuid4 is restored to original
    # But late_import_helper2.uuid4 is STILL the patched function
    original_uuid4 = uuid.uuid4
    module_uuid4 = late_import_helper2.get_uuid4_function()

    # BUG: module_uuid4 should be original_uuid4 but it's not
    assert module_uuid4 is not original_uuid4, (
        "BUG: Module's uuid4 is stale patched function, not original"
    )

def test_b_find_uuid4_imports_misses_module():
    '''Verify _find_uuid4_imports doesn't find the stale module.'''
    import late_import_helper2
    from pytest_uuid._tracking import _find_uuid4_imports

    original_uuid4 = uuid.uuid4
    module_uuid4 = late_import_helper2.get_uuid4_function()

    # The module's uuid4 is NOT the original function
    # So _find_uuid4_imports won't find it
    imports = _find_uuid4_imports(original_uuid4)
    module_names = [m.__name__ for m, _ in imports]

    # BUG: late_import_helper2 is NOT in the list
    assert "late_import_helper2" not in module_names, (
        "BUG: _find_uuid4_imports doesn't find module with stale uuid4"
    )
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=2)


def test_workaround_import_before_freeze_uuid(pytester):
    """Workaround: Import module BEFORE freeze_uuid context starts.

    This test demonstrates that importing at module level works correctly.
    """
    pytester.makepyfile(
        early_import_helper="""
from uuid import uuid4

def generate_uuid():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_early_import="""
import pytest
from pytest_uuid import freeze_uuid

# Import at module level - BEFORE any freeze_uuid context
import early_import_helper

def test_a_with_early_import():
    '''Test with module imported before freeze_uuid.'''
    with freeze_uuid(seed=42) as freezer:
        freezer.reset()
        uuid1 = early_import_helper.generate_uuid()
        freezer.reset()
        uuid1_again = early_import_helper.generate_uuid()
        assert uuid1 == uuid1_again, "Should be deterministic"

def test_b_still_works():
    '''Second test also works because module was imported early.'''
    with freeze_uuid(seed=99) as freezer:
        freezer.reset()
        uuid1 = early_import_helper.generate_uuid()
        freezer.reset()
        uuid1_again = early_import_helper.generate_uuid()
        # This WORKS because module was imported before any freeze_uuid
        assert uuid1 == uuid1_again, "Should be deterministic"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=2)