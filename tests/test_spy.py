"""Tests for spy functionality."""

from __future__ import annotations

import uuid

import pytest

from pytest_uuid.types import UUIDCall


class TestSpyUUID:
    """Tests for the spy_uuid fixture."""

    def test_spy_returns_real_uuids(self, spy_uuid):  # noqa: ARG002
        """Test that spy returns real random UUIDs."""
        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        # Real UUIDs should be different
        assert result1 != result2
        assert result1.version == 4
        assert result2.version == 4

    def test_spy_tracks_call_count(self, spy_uuid):
        """Test that spy tracks call count."""
        assert spy_uuid.call_count == 0

        uuid.uuid4()
        assert spy_uuid.call_count == 1

        uuid.uuid4()
        uuid.uuid4()
        assert spy_uuid.call_count == 3

    def test_spy_tracks_generated_uuids(self, spy_uuid):
        """Test that spy tracks all generated UUIDs."""
        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        assert spy_uuid.generated_uuids == [result1, result2]

    def test_spy_tracks_last_uuid(self, spy_uuid):
        """Test that spy tracks the last UUID."""
        assert spy_uuid.last_uuid is None

        result1 = uuid.uuid4()
        assert spy_uuid.last_uuid == result1

        result2 = uuid.uuid4()
        assert spy_uuid.last_uuid == result2

    def test_spy_reset(self, spy_uuid):
        """Test that spy reset clears tracking data."""
        uuid.uuid4()
        uuid.uuid4()

        spy_uuid.reset()

        assert spy_uuid.call_count == 0
        assert spy_uuid.generated_uuids == []
        assert spy_uuid.last_uuid is None

    def test_spy_generated_uuids_returns_copy(self, spy_uuid):
        """Test that generated_uuids returns a copy (defensive)."""
        uuid.uuid4()

        result = spy_uuid.generated_uuids
        result.clear()  # Modify the copy

        # Original should be unchanged
        assert len(spy_uuid.generated_uuids) == 1


class TestMockUUIDSpyMode:
    """Tests for mock_uuid spy mode."""

    def test_spy_method_returns_real_uuids(self, mock_uuid):
        """Test that spy mode returns real UUIDs."""
        mock_uuid.spy()

        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        assert result1 != result2
        assert result1.version == 4

    def test_spy_mode_still_tracks(self, mock_uuid):
        """Test that spy mode still tracks calls."""
        mock_uuid.spy()

        result = uuid.uuid4()

        assert mock_uuid.call_count == 1
        assert mock_uuid.last_uuid == result

    def test_spy_after_set(self, mock_uuid):
        """Test switching to spy mode after setting UUIDs."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        uuid.uuid4()  # Returns mocked

        mock_uuid.spy()
        result = uuid.uuid4()  # Returns real

        # Real UUID should be different from the mocked one
        assert result != uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert mock_uuid.call_count == 2

    def test_spy_mode_tracks_all_calls(self, mock_uuid):
        """Test that spy mode tracks all calls including before spy()."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        uuid.uuid4()  # Mocked call

        mock_uuid.spy()
        uuid.uuid4()  # Real call

        # Both calls should be tracked
        assert mock_uuid.call_count == 2
        assert len(mock_uuid.generated_uuids) == 2


class TestUUIDCallTracking:
    """Tests for detailed call tracking with UUIDCall dataclass."""

    def test_spy_uuid_calls_property(self, spy_uuid):
        """Test that spy_uuid tracks calls with metadata."""
        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        calls = spy_uuid.calls
        assert len(calls) == 2

        # All spy calls return real UUIDs (was_mocked=False)
        assert all(not c.was_mocked for c in calls)
        assert calls[0].uuid == result1
        assert calls[1].uuid == result2

    def test_spy_uuid_calls_have_caller_info(self, spy_uuid):
        """Test that spy_uuid captures caller module and file."""
        uuid.uuid4()

        calls = spy_uuid.calls
        assert len(calls) == 1

        call = calls[0]
        # Should capture this test module
        assert call.caller_module is not None
        assert "test_spy" in call.caller_module
        assert call.caller_file is not None
        assert call.caller_file.endswith(".py")

    def test_spy_uuid_calls_from_filter(self, spy_uuid):
        """Test filtering calls by module prefix."""
        uuid.uuid4()

        # Filter by this test module
        matching = spy_uuid.calls_from("tests")
        assert len(matching) == 1

        # Filter by non-matching prefix
        non_matching = spy_uuid.calls_from("nonexistent")
        assert len(non_matching) == 0

    def test_spy_uuid_calls_returns_copy(self, spy_uuid):
        """Test that calls property returns a defensive copy."""
        uuid.uuid4()

        calls = spy_uuid.calls
        calls.clear()

        # Original should be unchanged
        assert len(spy_uuid.calls) == 1

    def test_spy_uuid_reset_clears_calls(self, spy_uuid):
        """Test that reset clears the calls list."""
        uuid.uuid4()
        assert len(spy_uuid.calls) == 1

        spy_uuid.reset()
        assert len(spy_uuid.calls) == 0

    def test_mock_uuid_calls_property(self, mock_uuid):
        """Test that mock_uuid tracks calls with metadata."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        result = uuid.uuid4()

        calls = mock_uuid.calls
        assert len(calls) == 1

        call = calls[0]
        assert call.uuid == result
        assert call.was_mocked is True

    def test_mock_uuid_mocked_vs_real_calls(self, mock_uuid):
        """Test separation of mocked and real (spy mode) calls."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        mocked_result = uuid.uuid4()  # Mocked

        mock_uuid.spy()
        real_result = uuid.uuid4()  # Real

        # Check all calls
        assert mock_uuid.call_count == 2

        # Check mocked_calls
        mocked = mock_uuid.mocked_calls
        assert len(mocked) == 1
        assert mocked[0].uuid == mocked_result
        assert mocked[0].was_mocked is True

        # Check real_calls
        real = mock_uuid.real_calls
        assert len(real) == 1
        assert real[0].uuid == real_result
        assert real[0].was_mocked is False

    def test_mock_uuid_mocked_and_real_counts(self, mock_uuid):
        """Test mocked_count and real_count properties."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        uuid.uuid4()  # Mocked
        uuid.uuid4()  # Mocked

        mock_uuid.spy()
        uuid.uuid4()  # Real

        assert mock_uuid.mocked_count == 2
        assert mock_uuid.real_count == 1
        assert mock_uuid.call_count == 3

    def test_mock_uuid_calls_from_filter(self, mock_uuid):
        """Test filtering calls by module prefix."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        uuid.uuid4()

        # Filter by this test module
        matching = mock_uuid.calls_from("tests")
        assert len(matching) == 1
        assert matching[0].was_mocked is True

        # Filter by non-matching prefix
        non_matching = mock_uuid.calls_from("nonexistent")
        assert len(non_matching) == 0

    def test_mock_uuid_reset_clears_calls(self, mock_uuid):
        """Test that reset clears the calls list."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        uuid.uuid4()

        assert len(mock_uuid.calls) == 1
        assert mock_uuid.mocked_count == 1

        mock_uuid.reset()

        assert len(mock_uuid.calls) == 0
        assert mock_uuid.mocked_count == 0
        assert mock_uuid.real_count == 0


class TestUUIDCallDataclass:
    """Tests for UUIDCall dataclass."""

    def test_uuid_call_is_frozen(self):
        """Test that UUIDCall is immutable."""
        from dataclasses import FrozenInstanceError

        call = UUIDCall(
            uuid=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            was_mocked=True,
            caller_module="test_module",
            caller_file="/path/to/test.py",
        )

        # Attempting to modify should raise FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            call.was_mocked = False

    def test_uuid_call_fields(self):
        """Test UUIDCall field values."""
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        call = UUIDCall(
            uuid=test_uuid,
            was_mocked=True,
            caller_module="myapp.models",
            caller_file="/app/models.py",
        )

        assert call.uuid == test_uuid
        assert call.was_mocked is True
        assert call.caller_module == "myapp.models"
        assert call.caller_file == "/app/models.py"

    def test_uuid_call_optional_fields(self):
        """Test UUIDCall with optional fields as None."""
        test_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        call = UUIDCall(
            uuid=test_uuid,
            was_mocked=False,
        )

        assert call.uuid == test_uuid
        assert call.was_mocked is False
        assert call.caller_module is None
        assert call.caller_file is None
