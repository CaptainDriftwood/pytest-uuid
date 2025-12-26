"""Tests for the CallTrackingMixin."""

from __future__ import annotations

import uuid

from pytest_uuid._tracking import (
    CallTrackingMixin,
    _find_uuid4_imports,
    _get_caller_info,
)
from pytest_uuid.types import UUIDCall


class ConcreteTracker(CallTrackingMixin):
    """Concrete implementation of CallTrackingMixin for testing."""

    def __init__(self) -> None:
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []


class TestCallTrackingMixin:
    """Direct tests for CallTrackingMixin functionality."""

    def test_initial_state(self):
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

    def test_record_call_increments_count(self):
        """Test that _record_call increments call_count."""
        tracker = ConcreteTracker()
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")

        tracker._record_call(
            test_uuid, was_mocked=True, caller_module=None, caller_file=None
        )

        assert tracker.call_count == 1

    def test_record_call_tracks_uuid(self):
        """Test that _record_call adds UUID to generated_uuids."""
        tracker = ConcreteTracker()
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")

        tracker._record_call(
            test_uuid, was_mocked=True, caller_module=None, caller_file=None
        )

        assert tracker.generated_uuids == [test_uuid]
        assert tracker.last_uuid == test_uuid

    def test_record_call_creates_uuid_call(self):
        """Test that _record_call creates proper UUIDCall record."""
        tracker = ConcreteTracker()
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")

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

    def test_record_multiple_calls(self):
        """Test tracking multiple calls."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        uuid3 = uuid.UUID("33333333-3333-3333-3333-333333333333")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )
        tracker._record_call(
            uuid2, was_mocked=False, caller_module=None, caller_file=None
        )
        tracker._record_call(
            uuid3, was_mocked=True, caller_module=None, caller_file=None
        )

        assert tracker.call_count == 3
        assert tracker.generated_uuids == [uuid1, uuid2, uuid3]
        assert tracker.last_uuid == uuid3

    def test_mocked_calls_filters_correctly(self):
        """Test that mocked_calls only returns mocked calls."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )
        tracker._record_call(
            uuid2, was_mocked=False, caller_module=None, caller_file=None
        )

        mocked = tracker.mocked_calls
        assert len(mocked) == 1
        assert mocked[0].uuid == uuid1
        assert mocked[0].was_mocked is True

    def test_real_calls_filters_correctly(self):
        """Test that real_calls only returns non-mocked calls."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )
        tracker._record_call(
            uuid2, was_mocked=False, caller_module=None, caller_file=None
        )

        real = tracker.real_calls
        assert len(real) == 1
        assert real[0].uuid == uuid2
        assert real[0].was_mocked is False

    def test_mocked_count_and_real_count(self):
        """Test mocked_count and real_count properties."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        uuid3 = uuid.UUID("33333333-3333-3333-3333-333333333333")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )
        tracker._record_call(
            uuid2, was_mocked=False, caller_module=None, caller_file=None
        )
        tracker._record_call(
            uuid3, was_mocked=True, caller_module=None, caller_file=None
        )

        assert tracker.mocked_count == 2
        assert tracker.real_count == 1

    def test_calls_from_filters_by_module_prefix(self):
        """Test calls_from filters by module prefix."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        uuid3 = uuid.UUID("33333333-3333-3333-3333-333333333333")

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

    def test_calls_from_with_no_matches(self):
        """Test calls_from returns empty list when no matches."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module="myapp.models", caller_file=None
        )

        assert tracker.calls_from("nonexistent") == []

    def test_calls_from_handles_none_module(self):
        """Test calls_from handles None caller_module."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )

        # Should not raise, should return empty
        assert tracker.calls_from("myapp") == []

    def test_reset_tracking_clears_all_state(self):
        """Test that _reset_tracking clears all tracking state."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        uuid2 = uuid.UUID("22222222-2222-2222-2222-222222222222")

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

    def test_generated_uuids_returns_copy(self):
        """Test that generated_uuids returns a defensive copy."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )

        result = tracker.generated_uuids
        result.clear()  # Modify the copy

        # Original should be unchanged
        assert len(tracker.generated_uuids) == 1

    def test_calls_returns_copy(self):
        """Test that calls returns a defensive copy."""
        tracker = ConcreteTracker()
        uuid1 = uuid.UUID("11111111-1111-1111-1111-111111111111")

        tracker._record_call(
            uuid1, was_mocked=True, caller_module=None, caller_file=None
        )

        result = tracker.calls
        result.clear()  # Modify the copy

        # Original should be unchanged
        assert len(tracker.calls) == 1


class TestGetCallerInfo:
    """Tests for _get_caller_info helper function."""

    def test_returns_caller_module_and_file(self):
        """Test that _get_caller_info captures caller info."""
        module, file = _get_caller_info(skip_frames=1)

        assert module is not None
        assert "test_tracking" in module
        assert file is not None
        assert file.endswith(".py")

    def test_skip_frames_works(self):
        """Test that skip_frames parameter works correctly."""

        def inner():
            return _get_caller_info(skip_frames=2)

        module, _file = inner()

        # Should capture this test method, not inner()
        assert module is not None
        assert "test_tracking" in module


class TestFindUuid4Imports:
    """Tests for _find_uuid4_imports helper function."""

    def test_finds_direct_imports(self):
        """Test that _find_uuid4_imports finds modules with uuid4."""
        # uuid4 is imported at the top of this test file via uuid module
        original_uuid4 = uuid.uuid4
        imports = _find_uuid4_imports(original_uuid4)

        # Should find at least the uuid module itself
        module_names = [m.__name__ for m, _ in imports if hasattr(m, "__name__")]
        assert "uuid" in module_names

    def test_returns_empty_for_non_imported_function(self):
        """Test that non-imported function returns empty list."""

        def fake_uuid4():
            pass

        imports = _find_uuid4_imports(fake_uuid4)
        assert imports == []
