"""Tests for UUID1 mocking support."""

from __future__ import annotations

import uuid


class TestUUID1Mocker:
    """Tests for mock_uuid.uuid1 functionality."""

    def test_uuid1_set_returns_static_value(self, mock_uuid):
        """Test that uuid1.set() returns the specified UUID."""
        mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")
        result = uuid.uuid1()
        assert str(result) == "12345678-1234-1234-8234-567812345678"

    def test_uuid1_set_sequence(self, mock_uuid):
        """Test that uuid1.set() with multiple values cycles through them."""
        mock_uuid.uuid1.set(
            "11111111-1111-1111-8111-111111111111",
            "22222222-2222-2222-8222-222222222222",
        )
        assert str(uuid.uuid1()) == "11111111-1111-1111-8111-111111111111"
        assert str(uuid.uuid1()) == "22222222-2222-2222-8222-222222222222"
        # Cycles back
        assert str(uuid.uuid1()) == "11111111-1111-1111-8111-111111111111"

    def test_uuid1_call_tracking(self, mock_uuid):
        """Test that uuid1 calls are tracked."""
        mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")
        uuid.uuid1()
        uuid.uuid1()

        assert mock_uuid.uuid1.call_count == 2
        assert len(mock_uuid.uuid1.calls) == 2
        assert mock_uuid.uuid1.calls[0].was_mocked is True
        assert mock_uuid.uuid1.calls[0].uuid_version == 1

    def test_uuid1_real_passthrough(self, mock_uuid):
        """Test that uuid1 returns real values when not mocked."""
        # Access uuid1 mocker but don't set any value
        _ = mock_uuid.uuid1  # Initialize the mocker
        result = uuid.uuid1()

        # Should return a real uuid1 (version 1)
        assert result.version == 1
        assert mock_uuid.uuid1.call_count == 1
        assert mock_uuid.uuid1.calls[0].was_mocked is False

    def test_uuid1_seed(self, mock_uuid):
        """Test that uuid1.set_seed() produces reproducible values."""
        mock_uuid.uuid1.set_seed(42)
        first = uuid.uuid1()

        mock_uuid.uuid1.reset()
        mock_uuid.uuid1.set_seed(42)
        second = uuid.uuid1()

        assert first == second

    def test_uuid1_set_node(self, mock_uuid):
        """Test that set_node() affects real uuid1 generation."""
        test_node = 0x123456789ABC
        mock_uuid.uuid1.set_node(test_node)
        result = uuid.uuid1()

        # The node should be the fixed value
        assert result.node == test_node
        assert result.version == 1

    def test_uuid1_reset_clears_state(self, mock_uuid):
        """Test that reset() clears the uuid1 mocker state."""
        mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")
        mock_uuid.uuid1.set_node(0x123456789ABC)
        uuid.uuid1()

        mock_uuid.uuid1.reset()

        # After reset, should return real uuid1 values
        result = uuid.uuid1()
        assert result.version == 1
        assert mock_uuid.uuid1.call_count == 1  # Counter was reset

    def test_uuid1_spy_mode(self, mock_uuid):
        """Test that spy() returns real values but tracks calls."""
        mock_uuid.uuid1.spy()
        result = uuid.uuid1()

        assert result.version == 1
        assert mock_uuid.uuid1.call_count == 1
        assert mock_uuid.uuid1.calls[0].was_mocked is False


class TestUUID1AndUUID4Together:
    """Tests for using uuid1 and uuid4 mocking together."""

    def test_both_uuid1_and_uuid4_mocked(self, mock_uuid):
        """Test that uuid1 and uuid4 can be mocked independently."""
        mock_uuid.set("44444444-4444-4444-8444-444444444444")
        mock_uuid.uuid1.set("11111111-1111-1111-8111-111111111111")

        assert str(uuid.uuid4()) == "44444444-4444-4444-8444-444444444444"
        assert str(uuid.uuid1()) == "11111111-1111-1111-8111-111111111111"

    def test_uuid4_mocked_uuid1_real(self, mock_uuid):
        """Test mocking uuid4 while uuid1 returns real values."""
        mock_uuid.set("44444444-4444-4444-8444-444444444444")
        _ = mock_uuid.uuid1  # Initialize but don't mock

        uuid4_result = uuid.uuid4()
        uuid1_result = uuid.uuid1()

        assert str(uuid4_result) == "44444444-4444-4444-8444-444444444444"
        assert uuid1_result.version == 1
