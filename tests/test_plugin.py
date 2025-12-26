"""Tests for the pytest-uuid plugin."""

from __future__ import annotations

import uuid
from uuid import uuid4

import pytest


class TestMockUUID:
    """Tests for the mock_uuid fixture."""

    def test_set_single_uuid(self, mock_uuid):
        """Test setting a single UUID."""
        expected = "12345678-1234-5678-1234-567812345678"
        mock_uuid.set(expected)

        result = uuid.uuid4()

        assert str(result) == expected

    def test_works_with_direct_import(self, mock_uuid):
        """Test that mock works with 'from uuid import uuid4' pattern."""
        expected = "12345678-1234-5678-1234-567812345678"
        mock_uuid.set(expected)

        # Use the directly imported uuid4 function
        result = uuid4()

        assert str(result) == expected

    def test_set_single_uuid_as_uuid_object(self, mock_uuid):
        """Test setting a UUID using a UUID object."""
        expected = uuid.UUID("12345678-1234-5678-1234-567812345678")
        mock_uuid.set(expected)

        result = uuid.uuid4()

        assert result == expected

    def test_set_default_uuid(self, mock_uuid):
        """Test setting a default UUID."""
        default = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        mock_uuid.set_default(default)

        # All calls return the default
        assert str(uuid.uuid4()) == default
        assert str(uuid.uuid4()) == default
        assert str(uuid.uuid4()) == default

    def test_set_overrides_default(self, mock_uuid):
        """Test that set() overrides the default."""
        default = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        specific = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

        mock_uuid.set_default(default)
        mock_uuid.set(specific)

        assert str(uuid.uuid4()) == specific

    def test_reset_clears_everything(self, mock_uuid):
        """Test that reset() clears all configuration."""
        mock_uuid.set("12345678-1234-5678-1234-567812345678")
        mock_uuid.set_default("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

        mock_uuid.reset()

        # Should return a real random UUID now
        result = uuid.uuid4()
        assert result != uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert result != uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    def test_no_mock_returns_random_uuid(self, mock_uuid):  # noqa: ARG002
        """Test that without configuration, random UUIDs are returned."""
        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        # Should be valid UUIDs but different from each other
        assert isinstance(result1, uuid.UUID)
        assert isinstance(result2, uuid.UUID)
        assert result1 != result2


class TestMockUUIDFactory:
    """Tests for the mock_uuid_factory fixture."""

    def test_factory_mocks_specific_module(self, mock_uuid_factory):
        """Test that the factory can mock a specific module."""
        expected = "12345678-1234-5678-1234-567812345678"

        with mock_uuid_factory("uuid") as mocker:
            mocker.set(expected)
            # Access through the module to get the patched version
            result = uuid.uuid4()

        assert str(result) == expected

    def test_factory_returns_mocker_with_all_methods(self, mock_uuid_factory):
        """Test that the factory returns a fully functional mocker."""
        with mock_uuid_factory("uuid") as mocker:
            # Test set
            mocker.set("11111111-1111-1111-1111-111111111111")
            assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

            # Test reset
            mocker.reset()

            # Test set_default
            mocker.set_default("22222222-2222-2222-2222-222222222222")
            assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"


class TestPluginIntegration:
    """Integration tests for the plugin."""

    def test_fixture_is_available(self, mock_uuid):
        """Test that the mock_uuid fixture is automatically available."""
        assert mock_uuid is not None

    def test_factory_fixture_is_available(self, mock_uuid_factory):
        """Test that the mock_uuid_factory fixture is automatically available."""
        assert mock_uuid_factory is not None
        assert callable(mock_uuid_factory)

    # Note: Test isolation is thoroughly tested in test_pytester_integration.py::TestTestIsolation


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_set_call(self, mock_uuid):
        """Test calling set() with no arguments."""
        mock_uuid.set()  # Should not raise
        # Should return random UUIDs since no UUIDs were set
        result = uuid.uuid4()
        assert isinstance(result, uuid.UUID)

    def test_invalid_uuid_string_raises(self, mock_uuid):
        """Test that invalid UUID strings raise an error."""
        with pytest.raises(ValueError):
            mock_uuid.set("not-a-valid-uuid")

    def test_set_can_be_called_multiple_times(self, mock_uuid):
        """Test that calling set() multiple times replaces previous values."""
        mock_uuid.set("11111111-1111-1111-1111-111111111111")
        assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

        mock_uuid.set("22222222-2222-2222-2222-222222222222")
        assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"


class TestCallTrackingIntegration:
    """Integration tests for call tracking via mock_uuid fixture.

    Note: The CallTrackingMixin is thoroughly tested in test_tracking.py.
    These tests verify that mock_uuid properly integrates call tracking.
    """

    def test_tracking_works_with_mocked_uuids(self, mock_uuid):
        """Test that tracking works correctly with mocked UUIDs."""
        mock_uuid.set(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )

        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        assert mock_uuid.call_count == 2
        assert mock_uuid.generated_uuids == [result1, result2]
        assert mock_uuid.last_uuid == result2
        assert mock_uuid.mocked_count == 2
        assert all(c.was_mocked for c in mock_uuid.calls)

    def test_tracking_works_with_real_uuids(self, mock_uuid):
        """Test that tracking works when no mock is set (spy mode)."""
        result = uuid.uuid4()

        assert mock_uuid.call_count == 1
        assert mock_uuid.last_uuid == result
        assert mock_uuid.real_count == 1
