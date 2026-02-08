"""Tests for the import hook optimizations."""

from __future__ import annotations

import uuid

from pytest_uuid._import_hook import UUIDImportHook


def _fake_patched_uuid4() -> uuid.UUID:
    """Fake patched uuid4 for testing."""
    return uuid.UUID("12345678-1234-4678-8234-567812345678")


def _create_test_hook() -> UUIDImportHook:
    """Create a UUIDImportHook for testing."""
    original_uuid4 = uuid.uuid4
    patched_locations: list[tuple[object, str, object]] = []
    return UUIDImportHook(original_uuid4, _fake_patched_uuid4, patched_locations)


# --- Module ID caching tests ---


def test_scanned_modules_starts_empty():
    """Verify _scanned_modules set starts empty."""
    hook = _create_test_hook()
    assert len(hook._scanned_modules) == 0


def test_patch_module_adds_to_scanned_set():
    """Verify _patch_module adds module ID to scanned set."""
    hook = _create_test_hook()

    import json  # Use a stdlib module that doesn't have uuid4

    hook._patch_module(json)

    assert id(json) in hook._scanned_modules


def test_patch_module_skips_already_scanned():
    """Verify calling _patch_module twice doesn't re-scan."""
    hook = _create_test_hook()

    import json

    hook._patch_module(json)
    initial_size = len(hook._scanned_modules)

    # Patch again - should be a no-op
    hook._patch_module(json)

    assert len(hook._scanned_modules) == initial_size


def test_multiple_modules_all_cached():
    """Verify multiple different modules are all cached."""
    hook = _create_test_hook()

    import json
    import os
    import sys

    hook._patch_module(json)
    hook._patch_module(os)
    hook._patch_module(sys)

    assert id(json) in hook._scanned_modules
    assert id(os) in hook._scanned_modules
    assert id(sys) in hook._scanned_modules


# --- UUID module skip tests ---


def test_uuid_module_is_scanned_but_skipped():
    """Verify uuid module is added to scanned set but skipped early."""
    hook = _create_test_hook()

    hook._patch_module(uuid)

    # uuid module should be in scanned set
    assert id(uuid) in hook._scanned_modules


def test_uuid_module_not_in_patched_locations():
    """Verify uuid module attributes are not added to patched_locations."""
    hook = _create_test_hook()

    hook._patch_module(uuid)

    # No patched locations should reference the uuid module
    for module, _attr_name, _original in hook.patched_locations:
        assert module is not uuid, "uuid module should not be patched"
