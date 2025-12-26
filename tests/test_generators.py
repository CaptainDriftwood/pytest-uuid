"""Tests for UUID generators."""

from __future__ import annotations

import random
import uuid

import pytest

from pytest_uuid.generators import (
    ExhaustionBehavior,
    RandomUUIDGenerator,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDsExhaustedError,
    generate_uuid_from_random,
    parse_uuid,
    parse_uuids,
)


class TestGenerateUUIDFromRandom:
    """Tests for the generate_uuid_from_random function."""

    def test_generates_valid_uuid_v4(self):
        """Test that generated UUIDs are valid v4 UUIDs."""
        rng = random.Random(42)
        result = generate_uuid_from_random(rng)

        assert isinstance(result, uuid.UUID)
        assert result.version == 4
        assert result.variant == uuid.RFC_4122

    def test_reproducible_with_same_seed(self):
        """Test that same seed produces same UUIDs."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        uuid1 = generate_uuid_from_random(rng1)
        uuid2 = generate_uuid_from_random(rng2)

        assert uuid1 == uuid2

    def test_different_seeds_produce_different_uuids(self):
        """Test that different seeds produce different UUIDs."""
        rng1 = random.Random(42)
        rng2 = random.Random(43)

        uuid1 = generate_uuid_from_random(rng1)
        uuid2 = generate_uuid_from_random(rng2)

        assert uuid1 != uuid2

    def test_sequential_calls_produce_different_uuids(self):
        """Test that sequential calls produce different UUIDs."""
        rng = random.Random(42)

        uuid1 = generate_uuid_from_random(rng)
        uuid2 = generate_uuid_from_random(rng)

        assert uuid1 != uuid2


class TestStaticUUIDGenerator:
    """Tests for StaticUUIDGenerator."""

    def test_always_returns_same_uuid(self):
        """Test that the same UUID is always returned."""
        expected = uuid.UUID("12345678-1234-5678-1234-567812345678")
        generator = StaticUUIDGenerator(expected)

        for _ in range(10):
            assert generator() == expected

    def test_reset_does_nothing(self):
        """Test that reset doesn't affect the generator."""
        expected = uuid.UUID("12345678-1234-5678-1234-567812345678")
        generator = StaticUUIDGenerator(expected)

        generator()
        generator.reset()

        assert generator() == expected


class TestSequenceUUIDGenerator:
    """Tests for SequenceUUIDGenerator."""

    def test_returns_uuids_in_sequence(self):
        """Test that UUIDs are returned in sequence."""
        uuids = [
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
            uuid.UUID("33333333-3333-3333-3333-333333333333"),
        ]
        generator = SequenceUUIDGenerator(uuids)

        assert generator() == uuids[0]
        assert generator() == uuids[1]
        assert generator() == uuids[2]

    def test_cycle_behavior_loops_back(self):
        """Test that CYCLE behavior loops back to start."""
        uuids = [
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
        ]
        generator = SequenceUUIDGenerator(uuids, on_exhausted=ExhaustionBehavior.CYCLE)

        assert generator() == uuids[0]
        assert generator() == uuids[1]
        assert generator() == uuids[0]  # Cycles back
        assert generator() == uuids[1]

    def test_random_behavior_falls_back_to_random(self):
        """Test that RANDOM behavior generates random UUIDs after exhaustion."""
        uuids = [uuid.UUID("11111111-1111-1111-1111-111111111111")]
        rng = random.Random(42)
        generator = SequenceUUIDGenerator(
            uuids,
            on_exhausted=ExhaustionBehavior.RANDOM,
            fallback_rng=rng,
        )

        # First call returns the sequence UUID
        assert generator() == uuids[0]

        # Subsequent calls return random (but reproducible with seed) UUIDs
        random_uuid = generator()
        assert random_uuid != uuids[0]
        assert isinstance(random_uuid, uuid.UUID)
        assert random_uuid.version == 4

    def test_raise_behavior_raises_on_exhaustion(self):
        """Test that RAISE behavior raises UUIDsExhaustedError."""
        uuids = [uuid.UUID("11111111-1111-1111-1111-111111111111")]
        generator = SequenceUUIDGenerator(uuids, on_exhausted=ExhaustionBehavior.RAISE)

        # First call works
        assert generator() == uuids[0]

        # Second call raises
        with pytest.raises(UUIDsExhaustedError) as exc_info:
            generator()

        assert exc_info.value.count == 1
        assert "exhausted after 1 UUIDs" in str(exc_info.value)

    def test_is_exhausted_property(self):
        """Test the is_exhausted property."""
        uuids = [uuid.UUID("11111111-1111-1111-1111-111111111111")]
        generator = SequenceUUIDGenerator(uuids)

        assert not generator.is_exhausted
        generator()  # Consume the only UUID
        assert not generator.is_exhausted  # Still not exhausted yet
        generator()  # Now it cycles
        assert generator.is_exhausted

    def test_reset_restores_sequence(self):
        """Test that reset restores the sequence to the beginning."""
        uuids = [
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
        ]
        generator = SequenceUUIDGenerator(uuids)

        generator()  # First
        generator()  # Second
        generator.reset()

        assert generator() == uuids[0]  # Back to first

    def test_empty_sequence_returns_random(self):
        """Test that empty sequence falls back to random UUIDs."""
        rng = random.Random(42)
        generator = SequenceUUIDGenerator([], fallback_rng=rng)

        result = generator()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4


class TestSeededUUIDGenerator:
    """Tests for SeededUUIDGenerator."""

    def test_reproducible_with_integer_seed(self):
        """Test that integer seed produces reproducible UUIDs."""
        gen1 = SeededUUIDGenerator(42)
        gen2 = SeededUUIDGenerator(42)

        assert gen1() == gen2()
        assert gen1() == gen2()

    def test_reset_restarts_sequence(self):
        """Test that reset restarts the sequence."""
        generator = SeededUUIDGenerator(42)

        first = generator()
        generator()  # Skip one
        generator.reset()

        assert generator() == first

    def test_with_random_instance(self):
        """Test using a Random instance directly."""
        rng = random.Random(42)
        generator = SeededUUIDGenerator(rng)

        result = generator()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    def test_reset_with_random_instance_does_nothing(self):
        """Test that reset does nothing when using Random instance."""
        rng = random.Random(42)
        generator = SeededUUIDGenerator(rng)

        first = generator()
        generator.reset()  # Should do nothing

        # The next call continues the sequence
        assert generator() != first


class TestRandomUUIDGenerator:
    """Tests for RandomUUIDGenerator."""

    def test_generates_valid_uuids(self):
        """Test that valid UUIDs are generated."""
        generator = RandomUUIDGenerator()

        result = generator()
        assert isinstance(result, uuid.UUID)

    def test_each_call_returns_different_uuid(self):
        """Test that each call returns a different UUID."""
        generator = RandomUUIDGenerator()

        results = [generator() for _ in range(100)]
        assert len(set(results)) == 100

    def test_reset_does_nothing(self):
        """Test that reset doesn't affect the generator."""
        generator = RandomUUIDGenerator()

        generator()
        generator.reset()  # Should not raise
        generator()


class TestParseUUID:
    """Tests for parse_uuid function."""

    def test_parses_string(self):
        """Test parsing a UUID string."""
        result = parse_uuid("12345678-1234-5678-1234-567812345678")
        assert result == uuid.UUID("12345678-1234-5678-1234-567812345678")

    def test_returns_uuid_unchanged(self):
        """Test that UUID objects are returned unchanged."""
        original = uuid.UUID("12345678-1234-5678-1234-567812345678")
        result = parse_uuid(original)
        assert result is original

    def test_invalid_string_raises(self):
        """Test that invalid strings raise ValueError."""
        with pytest.raises(ValueError):
            parse_uuid("not-a-uuid")


class TestParseUUIDs:
    """Tests for parse_uuids function."""

    def test_parses_sequence_of_strings(self):
        """Test parsing a sequence of UUID strings."""
        result = parse_uuids(
            [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ]
        )
        assert result == [
            uuid.UUID("11111111-1111-1111-1111-111111111111"),
            uuid.UUID("22222222-2222-2222-2222-222222222222"),
        ]

    def test_parses_mixed_sequence(self):
        """Test parsing a sequence of strings and UUID objects."""
        result = parse_uuids(
            [
                "11111111-1111-1111-1111-111111111111",
                uuid.UUID("22222222-2222-2222-2222-222222222222"),
            ]
        )
        assert len(result) == 2
        assert all(isinstance(u, uuid.UUID) for u in result)

    def test_empty_sequence(self):
        """Test parsing an empty sequence."""
        result = parse_uuids([])
        assert result == []
