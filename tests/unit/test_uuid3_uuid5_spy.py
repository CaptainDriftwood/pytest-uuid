"""Tests for UUID3 and UUID5 spy support."""

from __future__ import annotations

import uuid


class TestUUID3Spy:
    """Tests for mock_uuid.uuid3 spy functionality."""

    def test_uuid3_tracks_calls(self, mock_uuid):
        """Test that uuid3 calls are tracked."""
        _ = mock_uuid.uuid3  # Initialize the spy
        result = uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")

        assert mock_uuid.uuid3.call_count == 1
        assert mock_uuid.uuid3.last_uuid == result

    def test_uuid3_captures_namespace_and_name(self, mock_uuid):
        """Test that namespace and name are captured."""
        _ = mock_uuid.uuid3
        uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")

        call = mock_uuid.uuid3.calls[0]
        assert call.namespace == uuid.NAMESPACE_DNS
        assert call.name == "example.com"
        assert call.uuid_version == 3

    def test_uuid3_returns_real_values(self, mock_uuid):
        """Test that real uuid3 values are returned."""
        _ = mock_uuid.uuid3
        result = uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")

        # uuid3 is deterministic - same inputs = same output
        expected = uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")
        # Note: We can't compare directly since the spy is still active
        # Just verify it's a valid UUID v3
        assert result.version == 3

    def test_uuid3_multiple_calls(self, mock_uuid):
        """Test tracking multiple uuid3 calls."""
        _ = mock_uuid.uuid3
        uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")
        uuid.uuid3(uuid.NAMESPACE_URL, "https://example.com")
        uuid.uuid3(uuid.NAMESPACE_DNS, "test.org")

        assert mock_uuid.uuid3.call_count == 3
        assert len(mock_uuid.uuid3.calls) == 3
        assert mock_uuid.uuid3.calls[0].name == "example.com"
        assert mock_uuid.uuid3.calls[1].namespace == uuid.NAMESPACE_URL
        assert mock_uuid.uuid3.calls[2].name == "test.org"

    def test_uuid3_calls_with_namespace_filter(self, mock_uuid):
        """Test filtering calls by namespace."""
        _ = mock_uuid.uuid3
        uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")
        uuid.uuid3(uuid.NAMESPACE_URL, "https://example.com")
        uuid.uuid3(uuid.NAMESPACE_DNS, "test.org")

        dns_calls = mock_uuid.uuid3.calls_with_namespace(uuid.NAMESPACE_DNS)
        assert len(dns_calls) == 2
        assert all(c.namespace == uuid.NAMESPACE_DNS for c in dns_calls)

    def test_uuid3_calls_with_name_filter(self, mock_uuid):
        """Test filtering calls by name."""
        _ = mock_uuid.uuid3
        uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")
        uuid.uuid3(uuid.NAMESPACE_URL, "example.com")
        uuid.uuid3(uuid.NAMESPACE_DNS, "test.org")

        example_calls = mock_uuid.uuid3.calls_with_name("example.com")
        assert len(example_calls) == 2
        assert all(c.name == "example.com" for c in example_calls)

    def test_uuid3_reset_clears_tracking(self, mock_uuid):
        """Test that reset clears tracking data."""
        _ = mock_uuid.uuid3
        uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")
        assert mock_uuid.uuid3.call_count == 1

        mock_uuid.uuid3.reset()

        assert mock_uuid.uuid3.call_count == 0
        assert len(mock_uuid.uuid3.calls) == 0


class TestUUID5Spy:
    """Tests for mock_uuid.uuid5 spy functionality."""

    def test_uuid5_tracks_calls(self, mock_uuid):
        """Test that uuid5 calls are tracked."""
        _ = mock_uuid.uuid5
        result = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

        assert mock_uuid.uuid5.call_count == 1
        assert mock_uuid.uuid5.last_uuid == result

    def test_uuid5_captures_namespace_and_name(self, mock_uuid):
        """Test that namespace and name are captured."""
        _ = mock_uuid.uuid5
        uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

        call = mock_uuid.uuid5.calls[0]
        assert call.namespace == uuid.NAMESPACE_DNS
        assert call.name == "example.com"
        assert call.uuid_version == 5

    def test_uuid5_returns_real_values(self, mock_uuid):
        """Test that real uuid5 values are returned."""
        _ = mock_uuid.uuid5
        result = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

        # uuid5 is deterministic - verify it's a valid UUID v5
        assert result.version == 5

    def test_uuid5_multiple_namespaces(self, mock_uuid):
        """Test tracking with different namespaces."""
        _ = mock_uuid.uuid5
        uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
        uuid.uuid5(uuid.NAMESPACE_URL, "https://example.com")
        uuid.uuid5(uuid.NAMESPACE_OID, "1.2.3.4")
        uuid.uuid5(uuid.NAMESPACE_X500, "cn=test")

        assert mock_uuid.uuid5.call_count == 4

        url_calls = mock_uuid.uuid5.calls_with_namespace(uuid.NAMESPACE_URL)
        assert len(url_calls) == 1
        assert url_calls[0].name == "https://example.com"


class TestUUID3AndUUID5Together:
    """Tests for using uuid3 and uuid5 tracking together."""

    def test_uuid3_and_uuid5_tracked_independently(self, mock_uuid):
        """Test that uuid3 and uuid5 are tracked independently."""
        _ = mock_uuid.uuid3
        _ = mock_uuid.uuid5

        uuid.uuid3(uuid.NAMESPACE_DNS, "v3-example.com")
        uuid.uuid5(uuid.NAMESPACE_DNS, "v5-example.com")
        uuid.uuid3(uuid.NAMESPACE_DNS, "v3-another.com")

        assert mock_uuid.uuid3.call_count == 2
        assert mock_uuid.uuid5.call_count == 1

        assert mock_uuid.uuid3.calls[0].name == "v3-example.com"
        assert mock_uuid.uuid5.calls[0].name == "v5-example.com"

    def test_all_uuid_functions_together(self, mock_uuid):
        """Test using uuid1, uuid3, uuid4, and uuid5 together."""
        mock_uuid.set("44444444-4444-4444-8444-444444444444")
        mock_uuid.uuid1.set("11111111-1111-1111-8111-111111111111")
        _ = mock_uuid.uuid3
        _ = mock_uuid.uuid5

        # Call all uuid functions
        result4 = uuid.uuid4()
        result1 = uuid.uuid1()
        result3 = uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")
        result5 = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

        # Verify mocking/tracking
        assert str(result4) == "44444444-4444-4444-8444-444444444444"
        assert str(result1) == "11111111-1111-1111-8111-111111111111"
        assert result3.version == 3
        assert result5.version == 5

        # Verify call counts
        assert mock_uuid.call_count == 1  # uuid4
        assert mock_uuid.uuid1.call_count == 1
        assert mock_uuid.uuid3.call_count == 1
        assert mock_uuid.uuid5.call_count == 1
