"""Tests for UUID6, UUID7, and UUID8 mocking support.

These tests require Python 3.14+ or the uuid6 backport package.
"""

from __future__ import annotations

import uuid

from pytest_uuid._compat import HAS_UUID6_7_8

# Import uuid6/uuid7/uuid8 from backport if available
if HAS_UUID6_7_8:
    from uuid6 import uuid6, uuid7, uuid8


import pytest

# Skip all tests if uuid6/7/8 not available
pytestmark = pytest.mark.skipif(
    not HAS_UUID6_7_8,
    reason="uuid6/uuid7/uuid8 requires Python 3.14+ or uuid6 package",
)


class TestUUID6Mocker:
    """Tests for mock_uuid.uuid6 functionality."""

    def test_uuid6_set_returns_static_value(self, mock_uuid):
        """Test that uuid6.set() returns the specified UUID."""
        mock_uuid.uuid6.set("12345678-1234-6234-8234-567812345678")
        result = uuid6()
        assert str(result) == "12345678-1234-6234-8234-567812345678"

    def test_uuid6_set_sequence(self, mock_uuid):
        """Test that uuid6.set() with multiple values cycles through them."""
        mock_uuid.uuid6.set(
            "11111111-1111-6111-8111-111111111111",
            "22222222-2222-6222-8222-222222222222",
        )
        assert str(uuid6()) == "11111111-1111-6111-8111-111111111111"
        assert str(uuid6()) == "22222222-2222-6222-8222-222222222222"
        # Cycles back
        assert str(uuid6()) == "11111111-1111-6111-8111-111111111111"

    def test_uuid6_call_tracking(self, mock_uuid):
        """Test that uuid6 calls are tracked."""
        mock_uuid.uuid6.set("12345678-1234-6234-8234-567812345678")
        uuid6()
        uuid6()

        assert mock_uuid.uuid6.call_count == 2
        assert len(mock_uuid.uuid6.calls) == 2
        assert mock_uuid.uuid6.calls[0].was_mocked is True
        assert mock_uuid.uuid6.calls[0].uuid_version == 6

    def test_uuid6_real_passthrough(self, mock_uuid):
        """Test that uuid6 returns real values when not mocked."""
        _ = mock_uuid.uuid6  # Initialize but don't mock
        result = uuid6()

        # Should return a real uuid6 (version 6)
        assert result.version == 6
        assert mock_uuid.uuid6.call_count == 1
        assert mock_uuid.uuid6.calls[0].was_mocked is False

    def test_uuid6_seed(self, mock_uuid):
        """Test that uuid6.set_seed() produces reproducible values."""
        mock_uuid.uuid6.set_seed(42)
        first = uuid6()

        mock_uuid.uuid6.reset()
        mock_uuid.uuid6.set_seed(42)
        second = uuid6()

        assert first == second

    def test_uuid6_set_node(self, mock_uuid):
        """Test that set_node() affects real uuid6 generation."""
        test_node = 0x123456789ABC
        mock_uuid.uuid6.set_node(test_node)
        result = uuid6()

        assert result.node == test_node
        assert result.version == 6


class TestUUID7Mocker:
    """Tests for mock_uuid.uuid7 functionality."""

    def test_uuid7_set_returns_static_value(self, mock_uuid):
        """Test that uuid7.set() returns the specified UUID."""
        mock_uuid.uuid7.set("12345678-1234-7234-8234-567812345678")
        result = uuid7()
        assert str(result) == "12345678-1234-7234-8234-567812345678"

    def test_uuid7_set_sequence(self, mock_uuid):
        """Test that uuid7.set() with multiple values cycles through them."""
        mock_uuid.uuid7.set(
            "11111111-1111-7111-8111-111111111111",
            "22222222-2222-7222-8222-222222222222",
        )
        assert str(uuid7()) == "11111111-1111-7111-8111-111111111111"
        assert str(uuid7()) == "22222222-2222-7222-8222-222222222222"
        # Cycles back
        assert str(uuid7()) == "11111111-1111-7111-8111-111111111111"

    def test_uuid7_call_tracking(self, mock_uuid):
        """Test that uuid7 calls are tracked."""
        mock_uuid.uuid7.set("12345678-1234-7234-8234-567812345678")
        uuid7()
        uuid7()

        assert mock_uuid.uuid7.call_count == 2
        assert len(mock_uuid.uuid7.calls) == 2
        assert mock_uuid.uuid7.calls[0].was_mocked is True
        assert mock_uuid.uuid7.calls[0].uuid_version == 7

    def test_uuid7_real_passthrough(self, mock_uuid):
        """Test that uuid7 returns real values when not mocked."""
        _ = mock_uuid.uuid7  # Initialize but don't mock
        result = uuid7()

        # Should return a real uuid7 (version 7)
        assert result.version == 7
        assert mock_uuid.uuid7.call_count == 1
        assert mock_uuid.uuid7.calls[0].was_mocked is False

    def test_uuid7_seed(self, mock_uuid):
        """Test that uuid7.set_seed() produces reproducible values."""
        mock_uuid.uuid7.set_seed(42)
        first = uuid7()

        mock_uuid.uuid7.reset()
        mock_uuid.uuid7.set_seed(42)
        second = uuid7()

        assert first == second

    def test_uuid7_monotonic_when_not_mocked(self, mock_uuid):
        """Test that real uuid7 values are monotonic."""
        _ = mock_uuid.uuid7  # Initialize but don't mock

        # Generate several uuid7 values quickly
        values = [uuid7() for _ in range(5)]

        # They should be monotonically increasing (uuid7 guarantees this)
        for i in range(len(values) - 1):
            # Compare as integers (bytes representation)
            assert values[i].int < values[i + 1].int


class TestUUID8Mocker:
    """Tests for mock_uuid.uuid8 functionality."""

    def test_uuid8_set_returns_static_value(self, mock_uuid):
        """Test that uuid8.set() returns the specified UUID."""
        mock_uuid.uuid8.set("12345678-1234-8234-8234-567812345678")
        result = uuid8()
        assert str(result) == "12345678-1234-8234-8234-567812345678"

    def test_uuid8_set_sequence(self, mock_uuid):
        """Test that uuid8.set() with multiple values cycles through them."""
        mock_uuid.uuid8.set(
            "11111111-1111-8111-8111-111111111111",
            "22222222-2222-8222-8222-222222222222",
        )
        assert str(uuid8()) == "11111111-1111-8111-8111-111111111111"
        assert str(uuid8()) == "22222222-2222-8222-8222-222222222222"
        # Cycles back
        assert str(uuid8()) == "11111111-1111-8111-8111-111111111111"

    def test_uuid8_call_tracking(self, mock_uuid):
        """Test that uuid8 calls are tracked."""
        mock_uuid.uuid8.set("12345678-1234-8234-8234-567812345678")
        uuid8()
        uuid8()

        assert mock_uuid.uuid8.call_count == 2
        assert len(mock_uuid.uuid8.calls) == 2
        assert mock_uuid.uuid8.calls[0].was_mocked is True
        assert mock_uuid.uuid8.calls[0].uuid_version == 8

    def test_uuid8_real_passthrough(self, mock_uuid):
        """Test that uuid8 returns real values when not mocked."""
        _ = mock_uuid.uuid8  # Initialize but don't mock
        result = uuid8()

        # Should return a real uuid8 (version 8)
        assert result.version == 8
        assert mock_uuid.uuid8.call_count == 1
        assert mock_uuid.uuid8.calls[0].was_mocked is False

    def test_uuid8_seed(self, mock_uuid):
        """Test that uuid8.set_seed() produces reproducible values."""
        mock_uuid.uuid8.set_seed(42)
        first = uuid8()

        mock_uuid.uuid8.reset()
        mock_uuid.uuid8.set_seed(42)
        second = uuid8()

        assert first == second


class TestAllUUIDVersionsTogether:
    """Tests for using multiple UUID versions together."""

    def test_all_versions_mocked_independently(self, mock_uuid):
        """Test that all UUID versions can be mocked independently."""
        mock_uuid.uuid4.set("44444444-4444-4444-8444-444444444444")
        mock_uuid.uuid1.set("11111111-1111-1111-8111-111111111111")
        mock_uuid.uuid6.set("66666666-6666-6666-8666-666666666666")
        mock_uuid.uuid7.set("77777777-7777-7777-8777-777777777777")
        mock_uuid.uuid8.set("88888888-8888-8888-8888-888888888888")

        assert str(uuid.uuid4()) == "44444444-4444-4444-8444-444444444444"
        assert str(uuid.uuid1()) == "11111111-1111-1111-8111-111111111111"
        assert str(uuid6()) == "66666666-6666-6666-8666-666666666666"
        assert str(uuid7()) == "77777777-7777-7777-8777-777777777777"
        assert str(uuid8()) == "88888888-8888-8888-8888-888888888888"

    def test_call_counts_independent(self, mock_uuid):
        """Test that call counts are tracked independently per version."""
        mock_uuid.uuid4.set("44444444-4444-4444-8444-444444444444")
        mock_uuid.uuid1.set("11111111-1111-1111-8111-111111111111")
        mock_uuid.uuid7.set("77777777-7777-7777-8777-777777777777")

        # Call each version different number of times
        uuid.uuid4()
        uuid.uuid4()
        uuid.uuid1()
        uuid7()
        uuid7()
        uuid7()

        assert mock_uuid.uuid4.call_count == 2
        assert mock_uuid.uuid1.call_count == 1
        assert mock_uuid.uuid7.call_count == 3
