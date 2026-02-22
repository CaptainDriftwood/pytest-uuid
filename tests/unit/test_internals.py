"""Tests for internal/private functions in pytest-uuid."""

from __future__ import annotations

import types

from pytest_uuid.api import _should_ignore_frame

# --- _should_ignore_frame ---


def test_should_ignore_frame_empty_list_returns_false():
    """Test that empty ignore list always returns False."""
    # Create a mock frame with f_globals
    frame = types.SimpleNamespace(f_globals={"__name__": "mymodule"})
    assert _should_ignore_frame(frame, ()) is False


def test_should_ignore_frame_matching_prefix_returns_true():
    """Test that matching module prefix returns True."""
    frame = types.SimpleNamespace(f_globals={"__name__": "mymodule.submodule"})
    assert _should_ignore_frame(frame, ("mymodule",)) is True


def test_should_ignore_frame_non_matching_prefix_returns_false():
    """Test that non-matching module prefix returns False."""
    frame = types.SimpleNamespace(f_globals={"__name__": "othermodule"})
    assert _should_ignore_frame(frame, ("mymodule",)) is False


def test_should_ignore_frame_multiple_prefixes_any_match():
    """Test that any matching prefix returns True."""
    frame = types.SimpleNamespace(f_globals={"__name__": "package_b.module"})
    assert _should_ignore_frame(frame, ("package_a", "package_b")) is True


def test_should_ignore_frame_without_name_returns_false():
    """Test that frame without __name__ returns False."""
    frame = types.SimpleNamespace(f_globals={})
    assert _should_ignore_frame(frame, ("mymodule",)) is False


def test_should_ignore_frame_without_f_globals_returns_false():
    """Test that frame without f_globals attribute returns False."""
    frame = types.SimpleNamespace()
    assert _should_ignore_frame(frame, ("mymodule",)) is False
