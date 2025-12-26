"""Tests for enhanced plugin features.

These are unit-style tests for the mock_uuid fixture methods.
Integration tests for markers and isolation are in test_pytester_integration.py.
"""

from __future__ import annotations

import random
import uuid

import pytest

from pytest_uuid.generators import ExhaustionBehavior, UUIDsExhaustedError


class TestUUIDMockerEnhanced:
    """Tests for enhanced UUIDMocker methods."""

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

    def test_set_exhaustion_behavior_string(self, mock_uuid):
        """Test setting exhaustion behavior with string."""
        mock_uuid.set_exhaustion_behavior("raise")
        mock_uuid.set(
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
        )

        uuid.uuid4()
        uuid.uuid4()

        with pytest.raises(UUIDsExhaustedError):
            uuid.uuid4()

    def test_set_exhaustion_behavior_enum(self, mock_uuid):
        """Test setting exhaustion behavior with enum."""
        mock_uuid.set_exhaustion_behavior(ExhaustionBehavior.RAISE)
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
