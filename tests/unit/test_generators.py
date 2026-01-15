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

# --- generate_uuid_from_random ---


def test_generate_uuid_from_random_produces_valid_uuid_v4():
    """Test that generated UUIDs are valid v4 UUIDs."""
    rng = random.Random(42)
    result = generate_uuid_from_random(rng)

    assert isinstance(result, uuid.UUID)
    assert result.version == 4
    assert result.variant == uuid.RFC_4122


@pytest.mark.parametrize(
    ("seed1", "seed2", "should_be_equal"),
    [
        (42, 42, True),
        (42, 43, False),
    ],
)
def test_generate_uuid_from_random_seed_reproducibility(seed1, seed2, should_be_equal):
    """Test UUID generation reproducibility with different seeds."""
    rng1 = random.Random(seed1)
    rng2 = random.Random(seed2)

    uuid1 = generate_uuid_from_random(rng1)
    uuid2 = generate_uuid_from_random(rng2)

    if should_be_equal:
        assert uuid1 == uuid2
    else:
        assert uuid1 != uuid2


def test_generate_uuid_from_random_sequential_calls_differ():
    """Test that sequential calls produce different UUIDs."""
    rng = random.Random(42)

    uuid1 = generate_uuid_from_random(rng)
    uuid2 = generate_uuid_from_random(rng)

    assert uuid1 != uuid2


# --- StaticUUIDGenerator ---


def test_static_generator_always_returns_same_uuid():
    """Test that the same UUID is always returned."""
    expected = uuid.UUID("12345678-1234-4678-8234-567812345678")
    generator = StaticUUIDGenerator(expected)

    for _ in range(10):
        assert generator() == expected


def test_static_generator_reset_does_nothing():
    """Test that reset doesn't affect the generator."""
    expected = uuid.UUID("12345678-1234-4678-8234-567812345678")
    generator = StaticUUIDGenerator(expected)

    generator()
    generator.reset()

    assert generator() == expected


# --- SequenceUUIDGenerator ---


def test_sequence_generator_returns_uuids_in_order():
    """Test that UUIDs are returned in sequence."""
    uuids = [
        uuid.UUID("11111111-1111-4111-8111-111111111111"),
        uuid.UUID("22222222-2222-4222-8222-222222222222"),
        uuid.UUID("33333333-3333-4333-8333-333333333333"),
    ]
    generator = SequenceUUIDGenerator(uuids)

    assert generator() == uuids[0]
    assert generator() == uuids[1]
    assert generator() == uuids[2]


@pytest.mark.parametrize(
    ("behavior", "should_raise"),
    [
        (ExhaustionBehavior.CYCLE, False),
        (ExhaustionBehavior.RANDOM, False),
        (ExhaustionBehavior.RAISE, True),
    ],
)
def test_sequence_generator_exhaustion_behavior(behavior, should_raise):
    """Test different exhaustion behaviors after sequence is consumed."""
    uuids = [uuid.UUID("11111111-1111-4111-8111-111111111111")]
    rng = random.Random(42)
    generator = SequenceUUIDGenerator(uuids, on_exhausted=behavior, fallback_rng=rng)

    # First call returns the sequence UUID
    assert generator() == uuids[0]

    # Second call triggers exhaustion behavior
    if should_raise:
        with pytest.raises(UUIDsExhaustedError) as exc_info:
            generator()
        assert exc_info.value.count == 1
        assert "exhausted after 1 UUIDs" in str(exc_info.value)
    else:
        result = generator()
        assert isinstance(result, uuid.UUID)
        if behavior == ExhaustionBehavior.CYCLE:
            assert result == uuids[0]  # Cycles back
        else:  # RANDOM
            assert result != uuids[0]
            assert result.version == 4


def test_sequence_generator_is_exhausted_property():
    """Test the is_exhausted property."""
    uuids = [uuid.UUID("11111111-1111-4111-8111-111111111111")]
    generator = SequenceUUIDGenerator(uuids)

    assert not generator.is_exhausted
    generator()  # Consume the only UUID
    assert not generator.is_exhausted  # Still not exhausted yet
    generator()  # Now it cycles
    assert generator.is_exhausted


def test_sequence_generator_reset_restores_sequence():
    """Test that reset restores the sequence to the beginning."""
    uuids = [
        uuid.UUID("11111111-1111-4111-8111-111111111111"),
        uuid.UUID("22222222-2222-4222-8222-222222222222"),
    ]
    generator = SequenceUUIDGenerator(uuids)

    generator()  # First
    generator()  # Second
    generator.reset()

    assert generator() == uuids[0]  # Back to first


@pytest.mark.parametrize(
    ("behavior", "should_raise"),
    [
        (ExhaustionBehavior.CYCLE, False),
        (ExhaustionBehavior.RANDOM, False),
        (ExhaustionBehavior.RAISE, True),
    ],
)
def test_sequence_generator_empty_sequence_exhaustion(behavior, should_raise):
    """Test exhaustion behavior with empty sequences."""
    rng = random.Random(42)
    generator = SequenceUUIDGenerator([], on_exhausted=behavior, fallback_rng=rng)

    assert not generator.is_exhausted

    if should_raise:
        with pytest.raises(UUIDsExhaustedError) as exc_info:
            generator()
        assert exc_info.value.count == 0
    else:
        result = generator()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4

    assert generator.is_exhausted


# --- SeededUUIDGenerator ---


def test_seeded_generator_reproducible_with_integer_seed():
    """Test that integer seed produces reproducible UUIDs."""
    gen1 = SeededUUIDGenerator(42)
    gen2 = SeededUUIDGenerator(42)

    assert gen1() == gen2()
    assert gen1() == gen2()


def test_seeded_generator_reset_restarts_sequence():
    """Test that reset restarts the sequence."""
    generator = SeededUUIDGenerator(42)

    first = generator()
    generator()  # Skip one
    generator.reset()

    assert generator() == first


def test_seeded_generator_with_random_instance():
    """Test using a Random instance directly."""
    rng = random.Random(42)
    generator = SeededUUIDGenerator(rng)

    result = generator()
    assert isinstance(result, uuid.UUID)
    assert result.version == 4


def test_seeded_generator_reset_with_random_instance_does_nothing():
    """Test that reset does nothing when using Random instance."""
    rng = random.Random(42)
    generator = SeededUUIDGenerator(rng)

    first = generator()
    generator.reset()  # Should do nothing

    # The next call continues the sequence
    assert generator() != first


# --- RandomUUIDGenerator ---


def test_random_generator_produces_valid_uuids():
    """Test that valid UUIDs are generated."""
    generator = RandomUUIDGenerator()

    result = generator()
    assert isinstance(result, uuid.UUID)


def test_random_generator_each_call_returns_different_uuid():
    """Test that each call returns a different UUID."""
    generator = RandomUUIDGenerator()

    results = [generator() for _ in range(100)]
    assert len(set(results)) == 100


def test_random_generator_reset_does_nothing():
    """Test that reset doesn't affect the generator."""
    generator = RandomUUIDGenerator()

    generator()
    generator.reset()  # Should not raise
    generator()


# --- parse_uuid ---


@pytest.mark.parametrize(
    ("input_value", "expected_uuid"),
    [
        (
            "12345678-1234-4678-8234-567812345678",
            "12345678-1234-4678-8234-567812345678",
        ),
        (
            "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
            "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa",
        ),
    ],
)
def test_parse_uuid_parses_valid_string(input_value, expected_uuid):
    """Test parsing valid UUID strings."""
    result = parse_uuid(input_value)
    assert result == uuid.UUID(expected_uuid)


def test_parse_uuid_returns_uuid_unchanged():
    """Test that UUID objects are returned unchanged."""
    original = uuid.UUID("12345678-1234-4678-8234-567812345678")
    result = parse_uuid(original)
    assert result is original


@pytest.mark.parametrize(
    "invalid_input",
    [
        "not-a-uuid",
        "12345",
        "",
        "gggggggg-gggg-gggg-gggg-gggggggggggg",
    ],
)
def test_parse_uuid_invalid_string_raises(invalid_input):
    """Test that invalid strings raise ValueError."""
    with pytest.raises(ValueError):
        parse_uuid(invalid_input)


# --- parse_uuids ---


def test_parse_uuids_parses_sequence_of_strings():
    """Test parsing a sequence of UUID strings."""
    result = parse_uuids(
        [
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ]
    )
    assert result == [
        uuid.UUID("11111111-1111-4111-8111-111111111111"),
        uuid.UUID("22222222-2222-4222-8222-222222222222"),
    ]


def test_parse_uuids_parses_mixed_sequence():
    """Test parsing a sequence of strings and UUID objects."""
    result = parse_uuids(
        [
            "11111111-1111-4111-8111-111111111111",
            uuid.UUID("22222222-2222-4222-8222-222222222222"),
        ]
    )
    assert len(result) == 2
    assert all(isinstance(u, uuid.UUID) for u in result)


def test_parse_uuids_empty_sequence():
    """Test parsing an empty sequence."""
    result = parse_uuids([])
    assert result == []
