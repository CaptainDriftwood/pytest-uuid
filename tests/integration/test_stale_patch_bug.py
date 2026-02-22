"""Integration tests for the proxy-based patching approach.

This file verifies that the proxy approach correctly handles:
1. Modules imported at any time (before, during, after freeze_uuid)
2. Multiple freeze_uuid contexts with the same module
3. Deterministic UUID generation across contexts

The proxy approach eliminates the "stale patch" bug entirely because:
- uuid.uuid4 is permanently the proxy
- Any code capturing uuid4 gets the proxy
- The proxy delegates to the current context's generator at call time
"""

from __future__ import annotations


def test_late_import_is_deterministic(pytester):
    """Module imported during freeze_uuid works in subsequent contexts.

    With the proxy approach:
    1. test_a imports a module DURING freeze_uuid context
    2. test_b uses the same module with a different freeze_uuid
    3. Both get deterministic UUIDs because all calls go through the proxy
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
        test_late_import="""
import sys
import pytest
from pytest_uuid import freeze_uuid

def test_a_import_during_freeze():
    '''Test A: Import module during freeze_uuid context.'''
    # Remove from cache to ensure fresh import
    if "late_import_helper" in sys.modules:
        del sys.modules["late_import_helper"]

    with freeze_uuid(seed=42) as freezer:
        # Import DURING freeze_uuid context - gets the proxy
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
        # Works via proxy - no module-level patching needed
        freezer.reset()
        uuid1 = late_import_helper.generate_uuid()
        freezer.reset()
        uuid2 = late_import_helper.generate_uuid()

        # UUIDs are deterministic via proxy
        assert uuid1 == uuid2, "UUIDs should be deterministic via proxy"
"""
    )

    # Run tests in order (disable random ordering)
    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=2)


def test_module_works_across_many_contexts(pytester):
    """Module works correctly across many freeze_uuid contexts."""
    pytester.makepyfile(
        helper_module="""
from uuid import uuid4

def generate_uuid():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_many_contexts="""
import sys
from pytest_uuid import freeze_uuid

def test_many_contexts():
    '''Use same module across multiple freeze_uuid contexts.'''
    if "helper_module" in sys.modules:
        del sys.modules["helper_module"]

    # Context 1: Import the module
    with freeze_uuid(seed=1) as f1:
        import helper_module
        f1.reset()
        uuid_1 = helper_module.generate_uuid()

    # Context 2-5: Use the same module
    for seed in [2, 3, 4, 5]:
        with freeze_uuid(seed=seed) as f:
            f.reset()
            uuid_a = helper_module.generate_uuid()
            f.reset()
            uuid_b = helper_module.generate_uuid()
            assert uuid_a == uuid_b, f"Seed {seed} should be deterministic"
"""
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_early_import_works(pytester):
    """Module imported before freeze_uuid works correctly."""
    pytester.makepyfile(
        early_import_helper="""
from uuid import uuid4

def generate_uuid():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_early_import="""
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

def test_b_with_same_module():
    '''Second test with same module.'''
    with freeze_uuid(seed=99) as freezer:
        freezer.reset()
        uuid1 = early_import_helper.generate_uuid()
        freezer.reset()
        uuid2 = early_import_helper.generate_uuid()
        assert uuid1 == uuid2, "Should be deterministic"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=2)


def test_different_seeds_produce_different_uuids(pytester):
    """Different seeds produce different UUIDs in different contexts."""
    pytester.makepyfile(
        uuid_helper="""
from uuid import uuid4

def generate_uuid():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_different_seeds="""
import sys
from pytest_uuid import freeze_uuid

def test_different_seeds():
    '''Different seeds should produce different UUIDs.'''
    if "uuid_helper" in sys.modules:
        del sys.modules["uuid_helper"]

    with freeze_uuid(seed=42) as f1:
        import uuid_helper
        f1.reset()
        uuid_42 = uuid_helper.generate_uuid()

    with freeze_uuid(seed=99) as f2:
        f2.reset()
        uuid_99 = uuid_helper.generate_uuid()

    # Different seeds should produce different UUIDs
    assert uuid_42 != uuid_99, "Different seeds should produce different UUIDs"
"""
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
