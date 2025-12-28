"""Tests for internal/private functions in pytest-uuid."""

from __future__ import annotations

import sys
import types
import uuid

from pytest_uuid.api import _find_uuid4_imports, _should_ignore_frame

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


# --- _find_uuid4_imports ---


def test_find_uuid4_imports_finds_direct_import():
    """Test that direct uuid4 imports are found."""
    original_uuid4 = uuid.uuid4
    imports = _find_uuid4_imports(original_uuid4)

    # Should find at least the uuid module itself
    modules_found = [mod for mod, _ in imports]
    assert uuid in modules_found


def test_find_uuid4_imports_skips_different_uuid4_object():
    """Test that different uuid4 objects are not matched."""

    # Create a fake uuid4 function
    def fake_uuid4():
        pass

    imports = _find_uuid4_imports(fake_uuid4)

    # Should not find the real uuid module since it has a different uuid4
    modules_found = [mod for mod, _ in imports]
    assert uuid not in modules_found


def test_find_uuid4_imports_handles_none_module_in_sys_modules():
    """Test that None modules in sys.modules are handled gracefully."""
    original_uuid4 = uuid.uuid4

    # Temporarily add a None module to sys.modules
    test_key = "_test_none_module_"
    original_value = sys.modules.get(test_key)
    try:
        sys.modules[test_key] = None  # type: ignore[assignment]
        # Should not raise
        imports = _find_uuid4_imports(original_uuid4)
        assert isinstance(imports, list)
    finally:
        if original_value is None:
            sys.modules.pop(test_key, None)
        else:
            sys.modules[test_key] = original_value


def test_find_uuid4_imports_handles_module_that_raises_on_dir():
    """Test that modules that raise on dir() are handled gracefully."""
    original_uuid4 = uuid.uuid4

    # Create a module that raises when dir() is called
    class BadModule(types.ModuleType):
        def __dir__(self):
            raise RuntimeError("Cannot list attributes")

    test_key = "_test_bad_dir_module_"
    bad_module = BadModule(test_key)
    original_value = sys.modules.get(test_key)
    try:
        sys.modules[test_key] = bad_module
        # Should not raise - the exception should be caught
        imports = _find_uuid4_imports(original_uuid4)
        assert isinstance(imports, list)
    finally:
        if original_value is None:
            sys.modules.pop(test_key, None)
        else:
            sys.modules[test_key] = original_value


def test_find_uuid4_imports_handles_module_that_raises_on_getattr():
    """Test that modules that raise on getattr are handled gracefully."""
    original_uuid4 = uuid.uuid4

    # Create a module that raises when accessing certain attributes
    class BadGetAttrModule(types.ModuleType):
        def __getattr__(self, name):
            if name == "uuid4":
                raise AttributeError("Cannot access uuid4")
            return super().__getattribute__(name)

    test_key = "_test_bad_getattr_module_"
    bad_module = BadGetAttrModule(test_key)
    # Add a uuid4 entry to make dir() return it
    bad_module.__dict__["uuid4"] = "dummy"
    original_value = sys.modules.get(test_key)
    try:
        sys.modules[test_key] = bad_module
        # Should not raise - the exception should be caught
        imports = _find_uuid4_imports(original_uuid4)
        assert isinstance(imports, list)
    finally:
        if original_value is None:
            sys.modules.pop(test_key, None)
        else:
            sys.modules[test_key] = original_value
