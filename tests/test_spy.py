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

    def test_spy_integrates_call_tracking(self, spy_uuid):
        """Test that spy_uuid properly integrates CallTrackingMixin.

        Note: The CallTrackingMixin is thoroughly tested in test_tracking.py.
        This test verifies the fixture properly uses the mixin.
        """
        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        assert spy_uuid.call_count == 2
        assert spy_uuid.generated_uuids == [result1, result2]
        assert spy_uuid.last_uuid == result2
        # All spy calls should be marked as not mocked
        assert all(not c.was_mocked for c in spy_uuid.calls)


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
    """Integration tests for UUIDCall tracking.

    Note: The CallTrackingMixin is thoroughly tested in test_tracking.py.
    These tests verify fixture-specific behavior and integration.
    """

    def test_calls_capture_caller_info(self, spy_uuid):
        """Test that calls capture caller module and file via _get_caller_info."""
        uuid.uuid4()

        calls = spy_uuid.calls
        assert len(calls) == 1

        call = calls[0]
        # Should capture this test module
        assert call.caller_module is not None
        assert "test_spy" in call.caller_module
        assert call.caller_file is not None
        assert call.caller_file.endswith(".py")

    def test_mocked_vs_real_calls_separation(self, mock_uuid):
        """Test separation of mocked and real (spy mode) calls."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        mocked_result = uuid.uuid4()  # Mocked

        mock_uuid.spy()
        real_result = uuid.uuid4()  # Real

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
