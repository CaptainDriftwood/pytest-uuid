"""Integration tests for Bug #31: Stale patched functions - NOW FIXED.

GitHub Issue: https://github.com/CaptainDriftwood/pytest-uuid/issues/31

This bug has been FIXED via the import hook mechanism. These tests verify:
1. Modules imported during freeze_uuid context are properly tracked
2. Their uuid4 is restored to original on __exit__
3. Subsequent freeze_uuid contexts correctly find and patch them
4. UUIDs are deterministic across multiple freeze_uuid contexts

The fix uses two mechanisms:
1. Import hook: Intercepts imports during freeze_uuid and tracks them
2. Stale patch detection: _find_uuid4_imports() now finds functions marked
   with _pytest_uuid_patched attribute from previous contexts
"""

from __future__ import annotations


def test_fixed_late_import_is_deterministic(pytester):
    """FIXED: Module imported during freeze_uuid now works in subsequent contexts.

    This test verifies the fix works:
    1. test_a imports a module DURING freeze_uuid context
    2. test_b uses the same module with a different freeze_uuid
    3. test_b now gets DETERMINISTIC UUIDs (bug is fixed)
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
        test_late_import_fixed="""
import sys
import pytest
from pytest_uuid import freeze_uuid

# NOTE: We do NOT import late_import_helper here!
# The fix ensures it works even when imported during freeze_uuid context.

def test_a_import_during_freeze():
    '''Test A: Import module during freeze_uuid context.'''
    # Remove from cache to ensure fresh import
    if "late_import_helper" in sys.modules:
        del sys.modules["late_import_helper"]

    with freeze_uuid(seed=42) as freezer:
        # Import DURING freeze_uuid context - import hook tracks it
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
        # FIXED: UUIDs are now deterministic because:
        # 1. Import hook tracked the module in test_a
        # 2. Module's uuid4 was restored to original on __exit__
        # 3. This context correctly finds and patches it
        freezer.reset()
        uuid1 = late_import_helper.generate_uuid()
        freezer.reset()
        uuid2 = late_import_helper.generate_uuid()

        # FIXED: UUIDs are now deterministic!
        assert uuid1 == uuid2, (
            "FIXED: UUIDs should be deterministic after fix"
        )
"""
    )

    # Run tests in order (disable random ordering)
    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=2)


def test_fixed_module_uuid4_is_restored_to_original(pytester):
    """FIXED: Verify module's uuid4 is restored to original after __exit__.

    This test verifies the fix: after freeze_uuid context exits,
    the module's uuid4 is restored to the original function.
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
        test_restored_function="""
import sys
import uuid
from pytest_uuid import freeze_uuid

def test_a_module_is_restored_after_exit():
    '''Import module during freeze_uuid, verify restoration on exit.'''
    if "late_import_helper2" in sys.modules:
        del sys.modules["late_import_helper2"]

    with freeze_uuid(seed=42):
        import late_import_helper2
        # Module's uuid4 is now the patched function

    # FIXED: After __exit__, module's uuid4 is restored to original
    # (import hook tracked and restored it)
    original_uuid4 = uuid.uuid4
    module_uuid4 = late_import_helper2.get_uuid4_function()

    # FIXED: module_uuid4 IS original_uuid4 now
    assert module_uuid4 is original_uuid4, (
        "FIXED: Module's uuid4 should be restored to original after __exit__"
    )

def test_b_find_uuid4_imports_finds_module():
    '''Verify _find_uuid4_imports finds the module (no longer stale).'''
    import late_import_helper2
    from pytest_uuid._tracking import _find_uuid4_imports

    original_uuid4 = uuid.uuid4
    module_uuid4 = late_import_helper2.get_uuid4_function()

    # FIXED: The module's uuid4 IS the original function now
    assert module_uuid4 is original_uuid4, "Module uuid4 should be original"

    imports = _find_uuid4_imports(original_uuid4)
    module_names = [m.__name__ for m, _ in imports]

    # FIXED: late_import_helper2 IS in the list
    assert "late_import_helper2" in module_names, (
        "FIXED: _find_uuid4_imports should find module with original uuid4"
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


def test_stale_function_restored_to_true_original(pytester):
    """Verify module's uuid4 is restored to TRUE original, not stale patched.

    This tests a bug where modules with stale patched functions were being
    "restored" to their stale value instead of the true original uuid.uuid4.

    The fix ensures that __enter__ always stores self._original_uuid4 as the
    restoration target, consistent with the import hook behavior.
    """
    pytester.makepyfile(
        helper_module="""
from uuid import uuid4

def generate():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_restoration="""
import sys
import uuid
from pytest_uuid import freeze_uuid

def test_restoration():
    # Clean slate
    if "helper_module" in sys.modules:
        del sys.modules["helper_module"]

    # Context A: Import during context
    with freeze_uuid(seed=1):
        import helper_module

    # Context B: Use module (would fail if stale function not handled)
    with freeze_uuid(seed=2):
        pass

    # After both contexts, module should have TRUE original
    assert helper_module.uuid4 is uuid.uuid4, (
        "Module's uuid4 should be true original, not stale patched function"
    )
"""
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
