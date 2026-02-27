"""Tests for UUID generators."""

from __future__ import annotations

import random
import uuid

import pytest

from pytest_uuid.generators import (
    ExhaustionBehavior,
    RandomUUID1Generator,
    RandomUUID6Generator,
    RandomUUID7Generator,
    RandomUUID8Generator,
    RandomUUIDGenerator,
    SeededUUID1Generator,
    SeededUUID6Generator,
    SeededUUID7Generator,
    SeededUUID8Generator,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDsExhaustedError,
    generate_uuid1_from_random,
    generate_uuid6_from_random,
    generate_uuid7_from_random,
    generate_uuid8_from_random,
    generate_uuid_from_random,
    get_seeded_generator,
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


def test_seeded_generator_seed_property_with_integer():
    """Test that seed property returns the integer seed."""
    generator = SeededUUIDGenerator(42)
    assert generator.seed == 42


def test_seeded_generator_seed_property_with_random_instance():
    """Test that seed property returns None when using Random instance."""
    rng = random.Random(42)
    generator = SeededUUIDGenerator(rng)
    assert generator.seed is None


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


# =============================================================================
# Version-specific UUID generation functions
# =============================================================================


class TestGenerateUUID1FromRandom:
    """Tests for generate_uuid1_from_random function."""

    def test_produces_valid_uuid_v1(self):
        """Test that generated UUIDs have correct version."""
        rng = random.Random(42)
        result = generate_uuid1_from_random(rng)

        assert isinstance(result, uuid.UUID)
        assert result.version == 1
        assert result.variant == uuid.RFC_4122

    def test_seed_reproducibility(self):
        """Test that same seed produces same UUID."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        uuid1 = generate_uuid1_from_random(rng1)
        uuid2 = generate_uuid1_from_random(rng2)

        assert uuid1 == uuid2

    def test_fixed_node_is_preserved(self):
        """Test that fixed node value is used."""
        rng = random.Random(42)
        fixed_node = 0x123456789ABC

        result = generate_uuid1_from_random(rng, node=fixed_node)
        assert result.node == fixed_node

    def test_fixed_clock_seq_is_preserved(self):
        """Test that fixed clock_seq value is used."""
        rng = random.Random(42)
        fixed_clock_seq = 0x1234  # 14-bit value

        result = generate_uuid1_from_random(rng, clock_seq=fixed_clock_seq)
        # Extract clock_seq from UUID (bits 62-76)
        clock_seq_extracted = result.clock_seq
        assert clock_seq_extracted == fixed_clock_seq


class TestGenerateUUID6FromRandom:
    """Tests for generate_uuid6_from_random function."""

    def test_produces_valid_uuid_v6(self):
        """Test that generated UUIDs have correct version."""
        rng = random.Random(42)
        result = generate_uuid6_from_random(rng)

        assert isinstance(result, uuid.UUID)
        assert result.version == 6
        assert result.variant == uuid.RFC_4122

    def test_seed_reproducibility(self):
        """Test that same seed produces same UUID."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        uuid1 = generate_uuid6_from_random(rng1)
        uuid2 = generate_uuid6_from_random(rng2)

        assert uuid1 == uuid2


class TestGenerateUUID7FromRandom:
    """Tests for generate_uuid7_from_random function."""

    def test_produces_valid_uuid_v7(self):
        """Test that generated UUIDs have correct version."""
        rng = random.Random(42)
        result = generate_uuid7_from_random(rng)

        assert isinstance(result, uuid.UUID)
        assert result.version == 7
        assert result.variant == uuid.RFC_4122

    def test_seed_reproducibility(self):
        """Test that same seed produces same UUID."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        uuid1 = generate_uuid7_from_random(rng1)
        uuid2 = generate_uuid7_from_random(rng2)

        assert uuid1 == uuid2


class TestGenerateUUID8FromRandom:
    """Tests for generate_uuid8_from_random function."""

    def test_produces_valid_uuid_v8(self):
        """Test that generated UUIDs have correct version."""
        rng = random.Random(42)
        result = generate_uuid8_from_random(rng)

        assert isinstance(result, uuid.UUID)
        assert result.version == 8
        assert result.variant == uuid.RFC_4122

    def test_seed_reproducibility(self):
        """Test that same seed produces same UUID."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        uuid1 = generate_uuid8_from_random(rng1)
        uuid2 = generate_uuid8_from_random(rng2)

        assert uuid1 == uuid2


# =============================================================================
# Version-specific seeded generators
# =============================================================================


class TestSeededUUID1Generator:
    """Tests for SeededUUID1Generator."""

    def test_reproducible_with_integer_seed(self):
        """Test that integer seed produces reproducible UUIDs."""
        gen1 = SeededUUID1Generator(42)
        gen2 = SeededUUID1Generator(42)

        assert gen1() == gen2()
        assert gen1() == gen2()

    def test_produces_v1_uuids(self):
        """Test that generated UUIDs are v1."""
        gen = SeededUUID1Generator(42)
        result = gen()
        assert result.version == 1

    def test_reset_restarts_sequence(self):
        """Test that reset restarts the sequence."""
        gen = SeededUUID1Generator(42)

        first = gen()
        gen()  # Skip one
        gen.reset()

        assert gen() == first

    def test_fixed_node_is_used(self):
        """Test that fixed node is used in generation."""
        fixed_node = 0x123456789ABC
        gen = SeededUUID1Generator(42, node=fixed_node)

        result = gen()
        assert result.node == fixed_node

    def test_seed_property(self):
        """Test seed property returns the seed value."""
        gen = SeededUUID1Generator(42)
        assert gen.seed == 42


class TestSeededUUID6Generator:
    """Tests for SeededUUID6Generator."""

    def test_reproducible_with_integer_seed(self):
        """Test that integer seed produces reproducible UUIDs."""
        gen1 = SeededUUID6Generator(42)
        gen2 = SeededUUID6Generator(42)

        assert gen1() == gen2()

    def test_produces_v6_uuids(self):
        """Test that generated UUIDs are v6."""
        gen = SeededUUID6Generator(42)
        result = gen()
        assert result.version == 6


class TestSeededUUID7Generator:
    """Tests for SeededUUID7Generator."""

    def test_reproducible_with_integer_seed(self):
        """Test that integer seed produces reproducible UUIDs."""
        gen1 = SeededUUID7Generator(42)
        gen2 = SeededUUID7Generator(42)

        assert gen1() == gen2()

    def test_produces_v7_uuids(self):
        """Test that generated UUIDs are v7."""
        gen = SeededUUID7Generator(42)
        result = gen()
        assert result.version == 7


class TestSeededUUID8Generator:
    """Tests for SeededUUID8Generator."""

    def test_reproducible_with_integer_seed(self):
        """Test that integer seed produces reproducible UUIDs."""
        gen1 = SeededUUID8Generator(42)
        gen2 = SeededUUID8Generator(42)

        assert gen1() == gen2()

    def test_produces_v8_uuids(self):
        """Test that generated UUIDs are v8."""
        gen = SeededUUID8Generator(42)
        result = gen()
        assert result.version == 8


# =============================================================================
# get_seeded_generator factory function
# =============================================================================


class TestGetSeededGenerator:
    """Tests for get_seeded_generator factory function."""

    @pytest.mark.parametrize(
        ("version", "expected_type"),
        [
            ("uuid1", SeededUUID1Generator),
            ("uuid4", SeededUUIDGenerator),
            ("uuid6", SeededUUID6Generator),
            ("uuid7", SeededUUID7Generator),
            ("uuid8", SeededUUID8Generator),
        ],
    )
    def test_returns_correct_generator_type(self, version, expected_type):
        """Test that correct generator type is returned for each version."""
        gen = get_seeded_generator(version, 42)
        assert isinstance(gen, expected_type)

    def test_uuid1_accepts_node_and_clock_seq(self):
        """Test that uuid1 generator accepts node and clock_seq."""
        gen = get_seeded_generator("uuid1", 42, node=0x123456789ABC, clock_seq=1234)
        result = gen()
        assert result.node == 0x123456789ABC

    def test_uuid6_accepts_node_and_clock_seq(self):
        """Test that uuid6 generator accepts node and clock_seq."""
        gen = get_seeded_generator("uuid6", 42, node=0x123456789ABC, clock_seq=1234)
        # Just verify it doesn't raise
        result = gen()
        assert result.version == 6

    def test_unknown_version_raises(self):
        """Test that unknown version raises ValueError."""
        with pytest.raises(ValueError, match="Seeded generation not supported"):
            get_seeded_generator("uuid3", 42)

    def test_reproducibility_via_factory(self):
        """Test that factory produces reproducible generators."""
        gen1 = get_seeded_generator("uuid4", 42)
        gen2 = get_seeded_generator("uuid4", 42)

        assert gen1() == gen2()


# =============================================================================
# RandomUUID*Generator classes (delegate to real uuid functions)
# =============================================================================


class TestRandomUUID1Generator:
    """Tests for RandomUUID1Generator."""

    def test_produces_valid_uuid_v1(self):
        """Test that generated UUIDs are valid v1 UUIDs."""
        gen = RandomUUID1Generator()
        result = gen()

        assert isinstance(result, uuid.UUID)
        assert result.version == 1
        assert result.variant == uuid.RFC_4122

    def test_each_call_returns_different_uuid(self):
        """Test that each call returns a different UUID."""
        gen = RandomUUID1Generator()

        results = [gen() for _ in range(10)]
        assert len(set(results)) == 10

    def test_fixed_node_is_preserved(self):
        """Test that fixed node value is used."""
        fixed_node = 0x123456789ABC
        gen = RandomUUID1Generator(node=fixed_node)

        result = gen()
        assert result.node == fixed_node

    def test_fixed_clock_seq_is_preserved(self):
        """Test that fixed clock_seq value is used."""
        fixed_clock_seq = 0x1234
        gen = RandomUUID1Generator(clock_seq=fixed_clock_seq)

        result = gen()
        assert result.clock_seq == fixed_clock_seq

    def test_reset_does_nothing(self):
        """Test that reset doesn't affect the generator."""
        gen = RandomUUID1Generator()

        gen()
        gen.reset()  # Should not raise
        result = gen()
        assert isinstance(result, uuid.UUID)


class TestRandomUUID6Generator:
    """Tests for RandomUUID6Generator."""

    def test_produces_valid_uuid_v6(self):
        """Test that generated UUIDs are valid v6 UUIDs."""
        gen = RandomUUID6Generator()
        result = gen()

        assert isinstance(result, uuid.UUID)
        assert result.version == 6
        assert result.variant == uuid.RFC_4122

    def test_each_call_returns_different_uuid(self):
        """Test that each call returns a different UUID."""
        gen = RandomUUID6Generator()

        results = [gen() for _ in range(10)]
        assert len(set(results)) == 10

    def test_fixed_node_is_preserved(self):
        """Test that fixed node value is used."""
        fixed_node = 0x123456789ABC
        gen = RandomUUID6Generator(node=fixed_node)

        result = gen()
        assert result.node == fixed_node

    def test_fixed_clock_seq_is_preserved(self):
        """Test that fixed clock_seq value is used."""
        fixed_clock_seq = 0x1234
        gen = RandomUUID6Generator(clock_seq=fixed_clock_seq)

        result = gen()
        assert result.clock_seq == fixed_clock_seq

    def test_reset_does_nothing(self):
        """Test that reset doesn't affect the generator."""
        gen = RandomUUID6Generator()

        gen()
        gen.reset()  # Should not raise
        result = gen()
        assert isinstance(result, uuid.UUID)


class TestRandomUUID7Generator:
    """Tests for RandomUUID7Generator."""

    def test_produces_valid_uuid_v7(self):
        """Test that generated UUIDs are valid v7 UUIDs."""
        gen = RandomUUID7Generator()
        result = gen()

        assert isinstance(result, uuid.UUID)
        assert result.version == 7
        assert result.variant == uuid.RFC_4122

    def test_each_call_returns_different_uuid(self):
        """Test that each call returns a different UUID."""
        gen = RandomUUID7Generator()

        results = [gen() for _ in range(10)]
        assert len(set(results)) == 10

    def test_reset_does_nothing(self):
        """Test that reset doesn't affect the generator."""
        gen = RandomUUID7Generator()

        gen()
        gen.reset()  # Should not raise
        result = gen()
        assert isinstance(result, uuid.UUID)


class TestRandomUUID8Generator:
    """Tests for RandomUUID8Generator."""

    def test_produces_valid_uuid_v8(self):
        """Test that generated UUIDs are valid v8 UUIDs."""
        gen = RandomUUID8Generator()
        result = gen()

        assert isinstance(result, uuid.UUID)
        assert result.version == 8
        assert result.variant == uuid.RFC_4122

    def test_each_call_returns_different_uuid(self):
        """Test that each call returns a different UUID."""
        gen = RandomUUID8Generator()

        results = [gen() for _ in range(10)]
        assert len(set(results)) == 10

    def test_reset_does_nothing(self):
        """Test that reset doesn't affect the generator."""
        gen = RandomUUID8Generator()

        gen()
        gen.reset()  # Should not raise
        result = gen()
        assert isinstance(result, uuid.UUID)


# =============================================================================
# Additional SeededUUID6Generator and SeededUUID7Generator tests
# =============================================================================


class TestSeededUUID6GeneratorExtended:
    """Extended tests for SeededUUID6Generator."""

    def test_reset_restarts_sequence(self):
        """Test that reset restarts the sequence."""
        gen = SeededUUID6Generator(42)

        first = gen()
        gen()  # Skip one
        gen.reset()

        assert gen() == first

    def test_seed_property_with_integer(self):
        """Test that seed property returns the integer seed."""
        gen = SeededUUID6Generator(42)
        assert gen.seed == 42

    def test_seed_property_with_random_instance(self):
        """Test that seed property returns None when using Random instance."""
        rng = random.Random(42)
        gen = SeededUUID6Generator(rng)
        assert gen.seed is None

    def test_reset_with_random_instance_does_nothing(self):
        """Test that reset does nothing when using Random instance."""
        rng = random.Random(42)
        gen = SeededUUID6Generator(rng)

        first = gen()
        gen.reset()  # Should do nothing

        # The next call continues the sequence
        assert gen() != first

    def test_fixed_node_is_used(self):
        """Test that fixed node is used in generation."""
        fixed_node = 0x123456789ABC
        gen = SeededUUID6Generator(42, node=fixed_node)

        result = gen()
        assert result.node == fixed_node

    def test_fixed_clock_seq_is_used(self):
        """Test that fixed clock_seq is used in generation."""
        fixed_clock_seq = 0x1234
        gen = SeededUUID6Generator(42, clock_seq=fixed_clock_seq)

        result = gen()
        assert result.clock_seq == fixed_clock_seq


class TestSeededUUID7GeneratorExtended:
    """Extended tests for SeededUUID7Generator."""

    def test_reset_restarts_sequence(self):
        """Test that reset restarts the sequence."""
        gen = SeededUUID7Generator(42)

        first = gen()
        gen()  # Skip one
        gen.reset()

        assert gen() == first

    def test_seed_property_with_integer(self):
        """Test that seed property returns the integer seed."""
        gen = SeededUUID7Generator(42)
        assert gen.seed == 42

    def test_seed_property_with_random_instance(self):
        """Test that seed property returns None when using Random instance."""
        rng = random.Random(42)
        gen = SeededUUID7Generator(rng)
        assert gen.seed is None

    def test_reset_with_random_instance_does_nothing(self):
        """Test that reset does nothing when using Random instance."""
        rng = random.Random(42)
        gen = SeededUUID7Generator(rng)

        first = gen()
        gen.reset()  # Should do nothing

        # The next call continues the sequence
        assert gen() != first


class TestSeededUUID8GeneratorExtended:
    """Extended tests for SeededUUID8Generator."""

    def test_reset_restarts_sequence(self):
        """Test that reset restarts the sequence."""
        gen = SeededUUID8Generator(42)

        first = gen()
        gen()  # Skip one
        gen.reset()

        assert gen() == first

    def test_seed_property_with_integer(self):
        """Test that seed property returns the integer seed."""
        gen = SeededUUID8Generator(42)
        assert gen.seed == 42

    def test_seed_property_with_random_instance(self):
        """Test that seed property returns None when using Random instance."""
        rng = random.Random(42)
        gen = SeededUUID8Generator(rng)
        assert gen.seed is None


# =============================================================================
# Additional generate_uuid6_from_random tests
# =============================================================================


class TestGenerateUUID6FromRandomExtended:
    """Extended tests for generate_uuid6_from_random function."""

    def test_fixed_node_is_preserved(self):
        """Test that fixed node value is used."""
        rng = random.Random(42)
        fixed_node = 0x123456789ABC

        result = generate_uuid6_from_random(rng, node=fixed_node)
        assert result.node == fixed_node

    def test_fixed_clock_seq_is_preserved(self):
        """Test that fixed clock_seq value is used."""
        rng = random.Random(42)
        fixed_clock_seq = 0x1234

        result = generate_uuid6_from_random(rng, clock_seq=fixed_clock_seq)
        assert result.clock_seq == fixed_clock_seq

    def test_fixed_node_and_clock_seq_together(self):
        """Test that both fixed node and clock_seq work together."""
        rng = random.Random(42)
        fixed_node = 0x123456789ABC
        fixed_clock_seq = 0x1234

        result = generate_uuid6_from_random(
            rng, node=fixed_node, clock_seq=fixed_clock_seq
        )
        assert result.node == fixed_node
        assert result.clock_seq == fixed_clock_seq
        assert result.version == 6
