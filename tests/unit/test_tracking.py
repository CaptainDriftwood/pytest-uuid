"""Tests for the CallTrackingMixin."""

from __future__ import annotations

import threading
import time
import uuid

import pytest

from pytest_uuid._tracking import (
    CallTrackingMixin,
    _find_uuid4_imports,
    _get_caller_info,
    _get_qualname,
)
from pytest_uuid.types import UUIDCall


class ConcreteTracker(CallTrackingMixin):
    """Concrete implementation of CallTrackingMixin for testing."""

    def __init__(self) -> None:
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []


# --- CallTrackingMixin ---


def test_tracking_initial_state():
    """Test that tracking starts with zero state."""
    tracker = ConcreteTracker()

    assert tracker.call_count == 0
    assert tracker.generated_uuids == []
    assert tracker.last_uuid is None
    assert tracker.calls == []
    assert tracker.mocked_calls == []
    assert tracker.real_calls == []
    assert tracker.mocked_count == 0
    assert tracker.real_count == 0


def test_tracking_record_call_increments_count():
    """Test that _record_call increments call_count."""
    tracker = ConcreteTracker()
    test_uuid = uuid.UUID("12345678-1234-4678-8234-567812345678")

    tracker._record_call(
        test_uuid, was_mocked=True, caller_module=None, caller_file=None
    )

    assert tracker.call_count == 1


def test_tracking_record_call_tracks_uuid():
    """Test that _record_call adds UUID to generated_uuids."""
    tracker = ConcreteTracker()
    test_uuid = uuid.UUID("12345678-1234-4678-8234-567812345678")

    tracker._record_call(
        test_uuid, was_mocked=True, caller_module=None, caller_file=None
    )

    assert tracker.generated_uuids == [test_uuid]
    assert tracker.last_uuid == test_uuid


def test_tracking_record_call_creates_uuid_call():
    """Test that _record_call creates proper UUIDCall record."""
    tracker = ConcreteTracker()
    test_uuid = uuid.UUID("12345678-1234-4678-8234-567812345678")

    tracker._record_call(
        test_uuid,
        was_mocked=True,
        caller_module="test_module",
        caller_file="/path/to/test.py",
    )

    assert len(tracker.calls) == 1
    call = tracker.calls[0]
    assert call.uuid == test_uuid
    assert call.was_mocked is True
    assert call.caller_module == "test_module"
    assert call.caller_file == "/path/to/test.py"


def test_tracking_record_multiple_calls():
    """Test tracking multiple calls."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
    uuid2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
    uuid3 = uuid.UUID("33333333-3333-4333-8333-333333333333")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)
    tracker._record_call(uuid2, was_mocked=False, caller_module=None, caller_file=None)
    tracker._record_call(uuid3, was_mocked=True, caller_module=None, caller_file=None)

    assert tracker.call_count == 3
    assert tracker.generated_uuids == [uuid1, uuid2, uuid3]
    assert tracker.last_uuid == uuid3


def test_tracking_mocked_calls_filters_correctly():
    """Test that mocked_calls only returns mocked calls."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
    uuid2 = uuid.UUID("22222222-2222-4222-8222-222222222222")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)
    tracker._record_call(uuid2, was_mocked=False, caller_module=None, caller_file=None)

    mocked = tracker.mocked_calls
    assert len(mocked) == 1
    assert mocked[0].uuid == uuid1
    assert mocked[0].was_mocked is True


def test_tracking_real_calls_filters_correctly():
    """Test that real_calls only returns non-mocked calls."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
    uuid2 = uuid.UUID("22222222-2222-4222-8222-222222222222")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)
    tracker._record_call(uuid2, was_mocked=False, caller_module=None, caller_file=None)

    real = tracker.real_calls
    assert len(real) == 1
    assert real[0].uuid == uuid2
    assert real[0].was_mocked is False


def test_tracking_mocked_count_and_real_count():
    """Test mocked_count and real_count properties."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
    uuid2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
    uuid3 = uuid.UUID("33333333-3333-4333-8333-333333333333")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)
    tracker._record_call(uuid2, was_mocked=False, caller_module=None, caller_file=None)
    tracker._record_call(uuid3, was_mocked=True, caller_module=None, caller_file=None)

    assert tracker.mocked_count == 2
    assert tracker.real_count == 1


def test_tracking_calls_from_filters_by_module_prefix():
    """Test calls_from filters by module prefix."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
    uuid2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
    uuid3 = uuid.UUID("33333333-3333-4333-8333-333333333333")

    tracker._record_call(
        uuid1, was_mocked=True, caller_module="myapp.models", caller_file=None
    )
    tracker._record_call(
        uuid2, was_mocked=True, caller_module="myapp.views", caller_file=None
    )
    tracker._record_call(
        uuid3, was_mocked=True, caller_module="other.module", caller_file=None
    )

    myapp_calls = tracker.calls_from("myapp")
    assert len(myapp_calls) == 2
    assert myapp_calls[0].caller_module == "myapp.models"
    assert myapp_calls[1].caller_module == "myapp.views"

    other_calls = tracker.calls_from("other")
    assert len(other_calls) == 1
    assert other_calls[0].caller_module == "other.module"


def test_tracking_calls_from_with_no_matches():
    """Test calls_from returns empty list when no matches."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")

    tracker._record_call(
        uuid1, was_mocked=True, caller_module="myapp.models", caller_file=None
    )

    assert tracker.calls_from("nonexistent") == []


def test_tracking_calls_from_handles_none_module():
    """Test calls_from handles None caller_module."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)

    # Should not raise, should return empty
    assert tracker.calls_from("myapp") == []


def test_tracking_reset_clears_all_state():
    """Test that _reset_tracking clears all tracking state."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
    uuid2 = uuid.UUID("22222222-2222-4222-8222-222222222222")

    tracker._record_call(
        uuid1, was_mocked=True, caller_module="test", caller_file="/test.py"
    )
    tracker._record_call(
        uuid2, was_mocked=False, caller_module="test", caller_file="/test.py"
    )

    tracker._reset_tracking()

    assert tracker.call_count == 0
    assert tracker.generated_uuids == []
    assert tracker.last_uuid is None
    assert tracker.calls == []
    assert tracker.mocked_calls == []
    assert tracker.real_calls == []
    assert tracker.mocked_count == 0
    assert tracker.real_count == 0


def test_tracking_generated_uuids_returns_copy():
    """Test that generated_uuids returns a defensive copy."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)

    result = tracker.generated_uuids
    result.clear()  # Modify the copy

    # Original should be unchanged
    assert len(tracker.generated_uuids) == 1


def test_tracking_calls_returns_copy():
    """Test that calls returns a defensive copy."""
    tracker = ConcreteTracker()
    uuid1 = uuid.UUID("11111111-1111-4111-8111-111111111111")

    tracker._record_call(uuid1, was_mocked=True, caller_module=None, caller_file=None)

    result = tracker.calls
    result.clear()  # Modify the copy

    # Original should be unchanged
    assert len(tracker.calls) == 1


# --- _get_caller_info ---


def test_get_caller_info_returns_module_and_file():
    """Test that _get_caller_info captures caller info."""
    module, file, line, function, qualname = _get_caller_info(skip_frames=1)

    assert module is not None
    assert "test_tracking" in module
    assert file is not None
    assert file.endswith(".py")
    assert line is not None
    assert isinstance(line, int)
    assert function == "test_get_caller_info_returns_module_and_file"
    assert qualname == "test_get_caller_info_returns_module_and_file"


def test_get_caller_info_skip_frames_works():
    """Test that skip_frames parameter works correctly."""

    def inner():
        return _get_caller_info(skip_frames=2)

    module, _file, _line, function, qualname = inner()

    # Should capture this test method, not inner()
    assert module is not None
    assert "test_tracking" in module
    assert function == "test_get_caller_info_skip_frames_works"
    assert qualname == "test_get_caller_info_skip_frames_works"


def test_get_caller_info_deep_call_stack():
    """Test _get_caller_info with deep call stack (10+ frames)."""

    def create_nested_caller(depth: int):
        """Create a chain of nested function calls."""
        if depth <= 0:
            # At the bottom, get caller info skipping all frames back to test
            return _get_caller_info(skip_frames=depth + 2)

        return create_nested_caller(depth - 1)

    # Test with 15 nested frames
    module, file, line, function, qualname = create_nested_caller(15)

    # Should still get valid caller info
    assert module is not None
    assert file is not None
    assert file.endswith(".py")
    assert line is not None
    assert function is not None
    assert qualname is not None


def test_get_caller_info_skip_frames_beyond_stack():
    """Test _get_caller_info when skip_frames exceeds stack depth."""
    # Skip more frames than exist in the stack
    module, file, line, function, qualname = _get_caller_info(skip_frames=1000)

    # Should return None for all values gracefully
    assert module is None
    assert file is None
    assert line is None
    assert function is None
    assert qualname is None


def test_get_caller_info_from_lambda():
    """Test _get_caller_info called from a lambda."""
    get_info = lambda: _get_caller_info(skip_frames=1)  # noqa: E731
    module, file, line, function, qualname = get_info()

    assert module is not None
    assert "test_tracking" in module
    assert file is not None
    assert line is not None
    assert function == "<lambda>"
    # qualname for lambda varies by Python version, but should not be None
    assert qualname is not None


def test_get_caller_info_from_nested_class():
    """Test _get_caller_info from within a nested class method."""

    class NestedClass:
        def get_caller_info(self):
            return _get_caller_info(skip_frames=1)

    obj = NestedClass()
    module, file, line, function, qualname = obj.get_caller_info()

    assert module is not None
    assert "test_tracking" in module
    assert file is not None
    assert line is not None
    assert function == "get_caller_info"
    # qualname should include class name
    assert "NestedClass" in qualname
    assert "get_caller_info" in qualname


def test_get_caller_info_from_builtin_callback():
    """Test _get_caller_info when called via builtin (map/filter)."""
    results = []

    def capture_info(_x):
        results.append(_get_caller_info(skip_frames=1))
        return True

    # Call through builtin filter
    list(filter(capture_info, [1]))

    assert len(results) == 1
    _module, file, line, function, qualname = results[0]
    # The frame should still be accessible
    assert file is not None
    assert line is not None
    assert function == "capture_info"
    assert qualname is not None


# --- _get_qualname ---


def test_get_qualname_from_instance_method():
    """Test _get_qualname correctly identifies instance methods via self."""
    import inspect

    class MyClass:
        def my_method(self):
            frame = inspect.currentframe()
            try:
                return _get_qualname(frame)
            finally:
                del frame

    obj = MyClass()
    qualname = obj.my_method()

    assert qualname is not None
    assert "MyClass" in qualname
    assert "my_method" in qualname


def test_get_qualname_from_classmethod():
    """Test _get_qualname correctly identifies classmethods via cls."""
    import inspect

    class MyClass:
        @classmethod
        def my_classmethod(cls):
            frame = inspect.currentframe()
            try:
                return _get_qualname(frame)
            finally:
                del frame

    qualname = MyClass.my_classmethod()

    assert qualname is not None
    assert "MyClass" in qualname
    assert "my_classmethod" in qualname


def test_get_qualname_from_staticmethod():
    """Test _get_qualname with staticmethod (no self/cls)."""
    import inspect

    class MyClass:
        @staticmethod
        def my_staticmethod():
            frame = inspect.currentframe()
            try:
                return _get_qualname(frame)
            finally:
                del frame

    qualname = MyClass.my_staticmethod()

    # Static methods don't have self/cls, so detection varies by Python version
    # On Python 3.11+, co_qualname gives full name
    # On Python 3.9/3.10, may only get simple name or gc-based detection
    assert qualname is not None
    assert "my_staticmethod" in qualname


def test_get_qualname_from_nested_class():
    """Test _get_qualname with nested class methods."""
    import inspect

    class Outer:
        class Inner:
            def inner_method(self):
                frame = inspect.currentframe()
                try:
                    return _get_qualname(frame)
                finally:
                    del frame

    obj = Outer.Inner()
    qualname = obj.inner_method()

    assert qualname is not None
    # Should contain both class names or at least the method name
    assert "inner_method" in qualname


def test_get_qualname_from_closure():
    """Test _get_qualname with closure/nested function."""
    import inspect

    def outer():
        def inner():
            frame = inspect.currentframe()
            try:
                return _get_qualname(frame)
            finally:
                del frame

        return inner()

    qualname = outer()

    assert qualname is not None
    assert "inner" in qualname


def test_get_qualname_from_module_level_function():
    """Test _get_qualname from a module-level function."""
    import inspect

    frame = inspect.currentframe()
    try:
        qualname = _get_qualname(frame)
    finally:
        del frame

    assert qualname is not None
    assert "test_get_qualname_from_module_level_function" in qualname


def test_get_qualname_with_none_frame():
    """Test _get_qualname returns None when frame is None."""
    # _get_qualname expects a frame, but we can test with edge cases
    # by checking how _get_caller_info handles it
    _module, _file, _line, _function, qualname = _get_caller_info(skip_frames=1000)

    # When frame is None, qualname should be None too
    assert qualname is None


def test_get_qualname_inherited_method():
    """Test _get_qualname with inherited methods.

    On Python 3.9/3.10, the fallback uses type(self).__qualname__ which gives
    Child.method instead of Parent.method. On Python 3.11+, co_qualname gives
    the actual defining class.
    """
    import inspect
    import sys

    class Parent:
        def inherited_method(self):
            frame = inspect.currentframe()
            try:
                return _get_qualname(frame)
            finally:
                del frame

    class Child(Parent):
        pass

    obj = Child()
    qualname = obj.inherited_method()

    assert qualname is not None
    # On Python 3.11+, this should be Parent.inherited_method
    # On Python 3.9/3.10, this will be Child.inherited_method (semantic difference)
    if sys.version_info >= (3, 11):
        assert "Parent" in qualname
    else:
        # On older versions, we get the runtime type, not defining class
        assert "Child" in qualname or "Parent" in qualname
    assert "inherited_method" in qualname


def test_get_qualname_lambda():
    """Test _get_qualname with lambda function."""
    import inspect

    get_qualname_from_lambda = lambda: _get_qualname(inspect.currentframe())  # noqa: E731

    qualname = get_qualname_from_lambda()

    assert qualname is not None
    assert "<lambda>" in qualname


def test_get_qualname_generator_function():
    """Test _get_qualname from within a generator function."""
    import inspect

    def my_generator():
        frame = inspect.currentframe()
        try:
            yield _get_qualname(frame)
        finally:
            del frame

    gen = my_generator()
    qualname = next(gen)

    assert qualname is not None
    assert "my_generator" in qualname


# --- _find_uuid4_imports ---


def test_find_uuid4_imports_finds_direct_imports():
    """Test that _find_uuid4_imports finds modules with uuid4."""
    # uuid4 is imported at the top of this test file via uuid module
    original_uuid4 = uuid.uuid4
    imports = _find_uuid4_imports(original_uuid4)

    # Should find at least the uuid module itself
    module_names = [m.__name__ for m, _ in imports if hasattr(m, "__name__")]
    assert "uuid" in module_names


def test_find_uuid4_imports_returns_empty_for_non_imported_function():
    """Test that non-imported function returns empty list."""

    def fake_uuid4():
        pass

    imports = _find_uuid4_imports(fake_uuid4)
    assert imports == []


def test_find_uuid4_imports_finds_dynamically_imported_module():
    """Test that _find_uuid4_imports finds uuid4 in dynamically imported modules."""
    import importlib

    # Dynamically import the uuid module with a fresh reference
    uuid_module = importlib.import_module("uuid")
    original_uuid4 = uuid_module.uuid4

    imports = _find_uuid4_imports(original_uuid4)

    # Should find the uuid module
    module_names = [m.__name__ for m, _ in imports if hasattr(m, "__name__")]
    assert "uuid" in module_names


def test_find_uuid4_imports_handles_custom_uuid4_attribute():
    """Test that modules with custom uuid4 attributes don't false-positive."""
    import sys
    import types

    # Create a fake module with a custom uuid4 function
    fake_module = types.ModuleType("fake_uuid_module")
    fake_module.uuid4 = lambda: "not a real uuid4"
    sys.modules["fake_uuid_module"] = fake_module

    try:
        # Looking for the real uuid4 should not find our fake module
        original_uuid4 = uuid.uuid4
        imports = _find_uuid4_imports(original_uuid4)

        module_names = [m.__name__ for m, _ in imports if hasattr(m, "__name__")]
        assert "fake_uuid_module" not in module_names
    finally:
        # Clean up
        del sys.modules["fake_uuid_module"]


def test_find_uuid4_imports_finds_same_reference():
    """Test that modules sharing the same uuid4 reference are found."""
    import sys
    import types

    # Create a module that has the real uuid4 as an attribute
    test_module = types.ModuleType("test_uuid_reference")
    test_module.uuid4 = uuid.uuid4  # Same reference as original
    sys.modules["test_uuid_reference"] = test_module

    try:
        original_uuid4 = uuid.uuid4
        imports = _find_uuid4_imports(original_uuid4)

        module_names = [m.__name__ for m, _ in imports if hasattr(m, "__name__")]
        assert "test_uuid_reference" in module_names
    finally:
        # Clean up
        del sys.modules["test_uuid_reference"]


def test_find_uuid4_imports_handles_module_without_dict():
    """Test that modules without __dict__ are handled gracefully."""
    import sys

    # Create a module-like object without proper __dict__
    class FakeModule:
        __name__ = "fake_no_dict"

        @property
        def __dict__(self):
            raise AttributeError("No dict here")

    fake = FakeModule()
    sys.modules["fake_no_dict"] = fake  # type: ignore[assignment]

    try:
        # Should not raise, should handle gracefully
        original_uuid4 = uuid.uuid4
        imports = _find_uuid4_imports(original_uuid4)

        # Result should be valid (not crash)
        assert isinstance(imports, list)
    finally:
        del sys.modules["fake_no_dict"]


def test_find_uuid4_imports_handles_none_in_sys_modules():
    """Test that None entries in sys.modules are handled."""
    import sys

    # sys.modules can contain None values for certain failed imports
    original_value = sys.modules.get("__none_test__")
    sys.modules["__none_test__"] = None  # type: ignore[assignment]

    try:
        original_uuid4 = uuid.uuid4
        # Should not raise
        imports = _find_uuid4_imports(original_uuid4)
        assert isinstance(imports, list)
    finally:
        if original_value is None:
            sys.modules.pop("__none_test__", None)
        else:
            sys.modules["__none_test__"] = original_value


# --- Thread Safety ---
# Note: These tests document current behavior (not thread-safe) rather than
# guaranteeing thread safety. The CallTrackingMixin explicitly documents
# that it is NOT thread-safe.


@pytest.mark.thread
def test_thread_concurrent_record_calls_high_thread_count():
    """Test _record_call from many concurrent threads.

    This test verifies that concurrent access doesn't crash, though
    exact counts may vary due to race conditions (which is expected).
    """
    tracker = ConcreteTracker()
    num_threads = 50
    calls_per_thread = 100
    errors = []

    def record_calls():
        try:
            for i in range(calls_per_thread):
                test_uuid = uuid.UUID(
                    f"{i:08x}-0000-0000-0000-{threading.current_thread().ident:012x}"[
                        :36
                    ]
                )
                tracker._record_call(
                    test_uuid,
                    was_mocked=True,
                    caller_module="test_thread",
                    caller_file="/test.py",
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=record_calls) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should not have raised any exceptions
    assert errors == [], f"Threads raised exceptions: {errors}"

    # Due to race conditions, we may not have exactly the expected count,
    # but we should have recorded some calls and not crashed
    assert tracker.call_count > 0
    assert len(tracker.generated_uuids) > 0
    assert len(tracker.calls) > 0


@pytest.mark.thread
def test_thread_concurrent_read_during_writes():
    """Test reading tracking data while concurrent writes are happening."""
    tracker = ConcreteTracker()
    stop_flag = threading.Event()
    errors = []
    read_counts = []

    def writer():
        i = 0
        while not stop_flag.is_set():
            test_uuid = uuid.UUID(f"{i:08x}-0000-0000-0000-000000000000")
            try:
                tracker._record_call(
                    test_uuid,
                    was_mocked=True,
                    caller_module="writer",
                    caller_file="/test.py",
                )
            except Exception as e:
                errors.append(("writer", e))
            i += 1
            time.sleep(0.001)  # Small delay to allow reads

    def reader():
        while not stop_flag.is_set():
            try:
                # These reads should not crash even during concurrent writes
                _ = tracker.call_count
                _ = tracker.generated_uuids
                _ = tracker.calls
                _ = tracker.last_uuid
                _ = tracker.mocked_calls
                _ = tracker.real_calls
                read_counts.append(1)
            except Exception as e:
                errors.append(("reader", e))
            time.sleep(0.001)

    # Start writer and multiple readers
    writer_thread = threading.Thread(target=writer)
    reader_threads = [threading.Thread(target=reader) for _ in range(5)]

    writer_thread.start()
    for t in reader_threads:
        t.start()

    # Let them run for a short time
    time.sleep(0.1)
    stop_flag.set()

    writer_thread.join()
    for t in reader_threads:
        t.join()

    # Should not have crashed
    assert errors == [], f"Threads raised exceptions: {errors}"
    # Readers should have successfully read multiple times
    assert len(read_counts) > 0


@pytest.mark.thread
@pytest.mark.slow
def test_thread_reset_during_concurrent_writes():
    """Test that reset can be called during concurrent writes without crashing."""
    tracker = ConcreteTracker()
    stop_flag = threading.Event()
    errors = []

    def writer():
        i = 0
        while not stop_flag.is_set():
            test_uuid = uuid.UUID(f"{i:08x}-0000-0000-0000-000000000000")
            try:
                tracker._record_call(
                    test_uuid,
                    was_mocked=True,
                    caller_module="writer",
                    caller_file="/test.py",
                )
            except Exception as e:
                errors.append(("writer", e))
            i += 1

    def resetter():
        while not stop_flag.is_set():
            try:
                tracker._reset_tracking()
            except Exception as e:
                errors.append(("resetter", e))
            time.sleep(0.01)

    writer_threads = [threading.Thread(target=writer) for _ in range(10)]
    resetter_thread = threading.Thread(target=resetter)

    for t in writer_threads:
        t.start()
    resetter_thread.start()

    time.sleep(0.1)
    stop_flag.set()

    for t in writer_threads:
        t.join()
    resetter_thread.join()

    # The main goal is to not crash
    assert errors == [], f"Threads raised exceptions: {errors}"


@pytest.mark.thread
def test_thread_calls_from_filter_during_writes():
    """Test calls_from filtering during concurrent writes."""
    tracker = ConcreteTracker()
    stop_flag = threading.Event()
    errors = []
    filter_results = []

    def writer():
        i = 0
        modules = ["myapp.models", "myapp.views", "other.module"]
        while not stop_flag.is_set():
            test_uuid = uuid.UUID(f"{i:08x}-0000-0000-0000-000000000000")
            try:
                tracker._record_call(
                    test_uuid,
                    was_mocked=True,
                    caller_module=modules[i % len(modules)],
                    caller_file="/test.py",
                )
            except Exception as e:
                errors.append(("writer", e))
            i += 1

    def filterer():
        while not stop_flag.is_set():
            try:
                result = tracker.calls_from("myapp")
                filter_results.append(len(result))
            except Exception as e:
                errors.append(("filterer", e))
            time.sleep(0.001)

    writer_thread = threading.Thread(target=writer)
    filterer_threads = [threading.Thread(target=filterer) for _ in range(3)]

    writer_thread.start()
    for t in filterer_threads:
        t.start()

    time.sleep(0.1)
    stop_flag.set()

    writer_thread.join()
    for t in filterer_threads:
        t.join()

    # Should not crash
    assert errors == [], f"Threads raised exceptions: {errors}"
    # Filter should have returned results (even if inconsistent due to races)
    assert len(filter_results) > 0
