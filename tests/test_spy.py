"""Tests for spy functionality."""

from __future__ import annotations

import uuid


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
