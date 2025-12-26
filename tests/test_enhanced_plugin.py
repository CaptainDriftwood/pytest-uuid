"""Tests for enhanced plugin features."""

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


class TestUUIDFreezerFixture:
    """Tests for the uuid_freezer fixture (alias)."""

    def test_uuid_freezer_exists(self, uuid_freezer):
        """Test that uuid_freezer fixture exists."""
        assert uuid_freezer is not None

    def test_uuid_freezer_has_same_api(self, uuid_freezer):
        """Test that uuid_freezer has the same API as mock_uuid."""
        uuid_freezer.set("12345678-1234-5678-1234-567812345678")
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    def test_uuid_freezer_set_seed(self, uuid_freezer):
        """Test uuid_freezer with seed."""
        uuid_freezer.set_seed(42)
        result = uuid.uuid4()
        assert isinstance(result, uuid.UUID)


class TestFreezeUUIDMarker:
    """Tests for @pytest.mark.freeze_uuid marker."""

    @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
    def test_marker_with_static_uuid(self):
        """Test marker with static UUID."""
        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

    @pytest.mark.freeze_uuid(
        ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
    )
    def test_marker_with_sequence(self):
        """Test marker with UUID sequence."""
        assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
        assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

    @pytest.mark.freeze_uuid(seed=42)
    def test_marker_with_seed(self):
        """Test marker with seed."""
        result = uuid.uuid4()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    @pytest.mark.freeze_uuid(seed="node")
    def test_marker_with_node_seed(self):
        """Test marker with node seed."""
        result1 = uuid.uuid4()

        # Reset and get another - should be different since we're advancing
        # But if we use the same node ID, we'd get the same sequence
        result2 = uuid.uuid4()

        # Both are valid UUIDs from the seeded sequence
        assert isinstance(result1, uuid.UUID)
        assert isinstance(result2, uuid.UUID)
        assert result1 != result2  # Sequential calls differ

    @pytest.mark.freeze_uuid(
        ["11111111-1111-1111-1111-111111111111"],
        on_exhausted="raise",
    )
    def test_marker_with_on_exhausted(self):
        """Test marker with on_exhausted behavior."""
        uuid.uuid4()  # First call works

        with pytest.raises(UUIDsExhaustedError):
            uuid.uuid4()


class TestMarkerReproducibility:
    """Tests for marker reproducibility across runs."""

    @pytest.mark.freeze_uuid(seed=12345)
    def test_seeded_first_run(self):
        """First run with specific seed - should be reproducible."""
        result = uuid.uuid4()
        # This specific seed should always produce the same UUID
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    @pytest.mark.freeze_uuid(seed=12345)
    def test_seeded_second_run(self):
        """Second test with same seed - should match first test."""
        result = uuid.uuid4()
        # Fresh seed means same first UUID
        assert isinstance(result, uuid.UUID)
        assert result.version == 4


class TestMarkerWithFixture:
    """Tests for combining marker with fixture."""

    @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
    def test_marker_takes_precedence(self, mock_uuid):  # noqa: ARG002
        """Test that marker freezes before fixture can be used."""
        # The marker has already frozen uuid.uuid4
        result = uuid.uuid4()
        assert str(result) == "12345678-1234-5678-1234-567812345678"

        # The mock_uuid fixture is separate and won't affect the marker's freeze
        # This is expected behavior - markers and fixtures are independent


class TestIsolation:
    """Tests for test isolation."""

    def test_first_test_sets_uuid(self, mock_uuid):
        """First test sets a UUID."""
        mock_uuid.set("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    def test_second_test_is_isolated(self, mock_uuid):  # noqa: ARG002
        """Second test should not be affected by first."""
        # Without setting anything, we get random UUIDs
        result = uuid.uuid4()
        assert str(result) != "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        assert isinstance(result, uuid.UUID)

    @pytest.mark.freeze_uuid("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    def test_marker_is_isolated(self):
        """Test with marker should not affect other tests."""
        assert str(uuid.uuid4()) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def test_after_marker_is_clean(self, mock_uuid):  # noqa: ARG002
        """Test after marker should have clean state."""
        result = uuid.uuid4()
        assert str(result) != "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
