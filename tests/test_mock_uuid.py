"""Tests for the mock_uuid fixture.

This file consolidates tests for all mock_uuid fixture functionality:
- Basic operations (set, set_default, reset)
- Enhanced features (set_seed, set_exhaustion_behavior)
- Factory fixture (mock_uuid_factory)
- Call tracking integration
"""

from __future__ import annotations

import random
import uuid
from uuid import uuid4

import pytest

from pytest_uuid.generators import ExhaustionBehavior, UUIDsExhaustedError


class TestMockUUIDBasic:
    """Tests for basic mock_uuid fixture operations."""

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


class TestMockUUIDEnhanced:
    """Tests for enhanced mock_uuid fixture methods (seed, exhaustion)."""

    def test_set_seed_integer(self, mock_uuid):
        """Test set_seed with integer seed."""
        mock_uuid.set_seed(42)
        first = uuid.uuid4()

        mock_uuid.set_seed(42)
        second = uuid.uuid4()

        assert first == second

    def test_set_seed_random_instance(self, mock_uuid):
        """Test set_seed with Random instance."""
        rng = random.Random(42)
        mock_uuid.set_seed(rng)

        result = uuid.uuid4()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    def test_set_seed_from_node(self, mock_uuid):
        """Test set_seed_from_node uses test node ID."""
        mock_uuid.set_seed_from_node()
        first = uuid.uuid4()

        mock_uuid.set_seed_from_node()
        second = uuid.uuid4()

        # Same test, same node ID, same seed
        assert first == second

    @pytest.mark.parametrize(
        "behavior_input",
        [
            "raise",
            ExhaustionBehavior.RAISE,
        ],
    )
    def test_set_exhaustion_behavior(self, mock_uuid, behavior_input):
        """Test setting exhaustion behavior with string or enum."""
        mock_uuid.set_exhaustion_behavior(behavior_input)
        mock_uuid.set("11111111-1111-1111-1111-111111111111")

        uuid.uuid4()

        with pytest.raises(UUIDsExhaustedError):
            uuid.uuid4()

    def test_generator_property(self, mock_uuid):
        """Test the generator property."""
        assert mock_uuid.generator is None

        mock_uuid.set_seed(42)
        assert mock_uuid.generator is not None

        mock_uuid.reset()
        assert mock_uuid.generator is None


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

    def test_factory_raises_keyerror_for_unloaded_module(self, mock_uuid_factory):
        """Test that factory raises helpful KeyError for unloaded modules."""
        with (
            pytest.raises(KeyError) as exc_info,
            mock_uuid_factory("nonexistent.module"),
        ):
            pass

        error_msg = str(exc_info.value)
        assert "nonexistent.module" in error_msg
        assert "not loaded" in error_msg

    def test_factory_raises_attributeerror_for_module_without_uuid4(
        self, mock_uuid_factory
    ):
        """Test that factory raises helpful AttributeError when module lacks uuid4."""
        # Use a module that exists but doesn't have uuid4 (sys is always loaded)
        with pytest.raises(AttributeError) as exc_info, mock_uuid_factory("sys"):
            pass

        error_msg = str(exc_info.value)
        assert "sys" in error_msg
        assert "uuid4" in error_msg
        assert "mock_uuid fixture" in error_msg


class TestPluginIntegration:
    """Integration tests for the plugin."""

    def test_fixture_is_available(self, mock_uuid):
        """Test that the mock_uuid fixture is automatically available."""
        assert mock_uuid is not None

    def test_factory_fixture_is_available(self, mock_uuid_factory):
        """Test that the mock_uuid_factory fixture is automatically available."""
        assert mock_uuid_factory is not None
        assert callable(mock_uuid_factory)


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
