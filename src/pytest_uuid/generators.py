"""UUID generation strategies for pytest-uuid.

This module provides the generator classes that produce UUIDs for mocking.
Each generator implements the UUIDGenerator protocol and can be used
internally by UUIDMocker and UUIDFreezer.

Generator Types:
    StaticUUIDGenerator: Always returns the same UUID. Used when you call
        mock_uuid.set() with a single UUID.

    SequenceUUIDGenerator: Returns UUIDs from a list in order. Used when
        you call mock_uuid.set() with multiple UUIDs. Behavior when the
        sequence is exhausted is controlled by ExhaustionBehavior.

    SeededUUIDGenerator: Produces reproducible UUIDs from a seed value.
        Used when you call mock_uuid.set_seed() or use seed="node".

    RandomUUIDGenerator: Delegates to the real uuid.uuid4(). Used internally
        when no mocking is configured but patching is still needed for the
        ignore list feature.

Extending:
    To create a custom generator, subclass UUIDGenerator and implement
    __call__() and reset(). Then pass your generator to UUIDMocker directly
    via its _generator attribute (advanced usage).
"""

from __future__ import annotations

import random
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class ExhaustionBehavior(Enum):
    """Controls behavior when a UUID sequence runs out of values.

    When using mock_uuid.set() with multiple UUIDs or freeze_uuid with a list,
    this determines what happens after all UUIDs have been returned once.

    Values:
        CYCLE: Loop back to the first UUID and repeat the sequence indefinitely.
            This is the default behavior. Use when you don't care about exact
            call counts or want infinite UUIDs from a small set.

        RANDOM: Switch to generating random valid UUID v4 values after the
            sequence is exhausted. Use when you need specific UUIDs for early
            calls but don't care about later ones.

        RAISE: Raise UUIDsExhaustedError when the sequence runs out. Use when
            you want to enforce that exactly N uuid4() calls happen in your
            test - any additional calls will fail the test.

    Example:
        mock_uuid.set_exhaustion_behavior("raise")
        mock_uuid.set("uuid1", "uuid2")
        uuid.uuid4()  # Returns uuid1
        uuid.uuid4()  # Returns uuid2
        uuid.uuid4()  # Raises UUIDsExhaustedError
    """

    CYCLE = "cycle"
    RANDOM = "random"
    RAISE = "raise"


class UUIDsExhaustedError(Exception):
    """Raised when UUID sequence is exhausted and behavior is RAISE."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(
            f"UUID sequence exhausted after {count} UUIDs. "
            "Set on_exhausted='cycle' or 'random' to continue generating."
        )


def generate_uuid_from_random(rng: random.Random) -> uuid.UUID:
    """Generate a valid UUID v4 using a seeded Random instance.

    The generated UUID is fully compliant with RFC 4122:
    - Version bits (76-79) are set to 4
    - Variant bits (62-63) are set to 10 (RFC 4122)

    Args:
        rng: A random.Random instance (can be seeded for reproducibility)

    Returns:
        A valid UUID v4 object
    """
    random_bits = rng.getrandbits(128)

    # UUID v4 structure (128 bits total, LSB numbering):
    #   Bits 0-47:   node (48 bits) - random
    #   Bits 48-55:  clock_seq_low (8 bits) - random
    #   Bits 56-61:  clock_seq_hi (6 bits) - random
    #   Bits 62-63:  variant (2 bits) - must be 10 for RFC 4122
    #   Bits 64-75:  time_hi (12 bits) - random
    #   Bits 76-79:  version (4 bits) - must be 0100 (4) for UUID v4
    #   Bits 80-95:  time_mid (16 bits) - random
    #   Bits 96-127: time_low (32 bits) - random

    # Set version to 4: clear bits 76-79 (0xF mask), then set to 4
    # Position 76 = 128 - 52 where version field starts in UUID spec
    random_bits = (random_bits & ~(0xF << 76)) | (4 << 76)

    # Set variant to RFC 4122 (binary 10): clear bits 62-63, then set to 2
    # Position 62 = 128 - 66 where variant field starts in UUID spec
    random_bits = (random_bits & ~(0x3 << 62)) | (0x2 << 62)

    return uuid.UUID(int=random_bits)


class UUIDGenerator(ABC):
    """Abstract base class for UUID generators.

    All generator classes inherit from this base and implement two methods:
    - __call__(): Generate and return the next UUID
    - reset(): Reset internal state to start the sequence over

    The generators are used internally by UUIDMocker and UUIDFreezer.
    Users typically don't instantiate generators directly; instead, use
    mock_uuid.set(), mock_uuid.set_seed(), or the freeze_uuid decorator.
    """

    @abstractmethod
    def __call__(self) -> uuid.UUID:
        """Generate and return the next UUID."""

    @abstractmethod
    def reset(self) -> None:
        """Reset the generator to its initial state.

        After reset(), the next __call__() will return the first UUID
        in the sequence (for SequenceUUIDGenerator) or restart the
        random sequence (for SeededUUIDGenerator with an integer seed).
        """


class StaticUUIDGenerator(UUIDGenerator):
    """Generator that always returns the same UUID.

    Used internally when mock_uuid.set() is called with a single UUID.
    Every call to __call__() returns the same UUID instance.

    Args:
        value: The UUID to return on every call.
    """

    def __init__(self, value: uuid.UUID) -> None:
        self._value = value

    def __call__(self) -> uuid.UUID:
        return self._value

    def reset(self) -> None:
        pass  # No state to reset


class SequenceUUIDGenerator(UUIDGenerator):
    """Generator that returns UUIDs from a sequence in order.

    Used internally when mock_uuid.set() is called with multiple UUIDs.
    Returns UUIDs in the order provided, then handles exhaustion according
    to the on_exhausted parameter.

    Args:
        uuids: Sequence of UUIDs to return in order.
        on_exhausted: Behavior when sequence is exhausted (default: CYCLE).
        fallback_rng: Random instance for RANDOM exhaustion behavior.

    Attributes:
        is_exhausted: True if the sequence has been fully consumed at least once.
    """

    def __init__(
        self,
        uuids: Sequence[uuid.UUID],
        on_exhausted: ExhaustionBehavior = ExhaustionBehavior.CYCLE,
        fallback_rng: random.Random | None = None,
    ) -> None:
        self._uuids = list(uuids)
        self._on_exhausted = on_exhausted
        self._fallback_rng = fallback_rng or random.Random()
        self._index = 0
        self._exhausted = False

    def __call__(self) -> uuid.UUID:
        if self._index < len(self._uuids):
            result = self._uuids[self._index]
            self._index += 1
            return result

        # Sequence exhausted (or was empty from the start)
        self._exhausted = True

        if self._on_exhausted == ExhaustionBehavior.CYCLE:
            if not self._uuids:
                # Empty sequence can't cycle - fall back to random
                return generate_uuid_from_random(self._fallback_rng)
            self._index = 1  # Reset to second element (we return first below)
            return self._uuids[0]
        if self._on_exhausted == ExhaustionBehavior.RANDOM:
            return generate_uuid_from_random(self._fallback_rng)
        # RAISE
        raise UUIDsExhaustedError(len(self._uuids))

    def reset(self) -> None:
        self._index = 0
        self._exhausted = False

    @property
    def is_exhausted(self) -> bool:
        """Whether the sequence has been fully consumed at least once."""
        return self._exhausted


class SeededUUIDGenerator(UUIDGenerator):
    """Generator that produces reproducible UUIDs from a seed.

    Used internally when mock_uuid.set_seed() is called or when using
    seed="node" with the freeze_uuid marker. Generates valid UUID v4 values
    deterministically from the seed.

    Args:
        seed: Either an integer seed (creates internal Random instance) or
            a random.Random instance (BYOP - bring your own randomizer).
            If a Random instance is provided, reset() will have no effect
            since the caller controls the random state.

    Note:
        The same seed always produces the same sequence of UUIDs, making
        tests reproducible. Different seeds produce different sequences.
    """

    def __init__(self, seed: int | random.Random) -> None:
        if isinstance(seed, random.Random):
            self._rng = seed
            self._seed = None  # Can't reset if given a Random instance
        else:
            self._seed = seed
            self._rng = random.Random(seed)

    def __call__(self) -> uuid.UUID:
        return generate_uuid_from_random(self._rng)

    def reset(self) -> None:
        if self._seed is not None:
            self._rng = random.Random(self._seed)
        # If initialized with a Random instance, reset does nothing
        # (user controls the state)

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation.

        Returns the integer seed if one was provided, or None if initialized
        with a random.Random instance (BYOP mode).
        """
        return self._seed


class RandomUUIDGenerator(UUIDGenerator):
    """Generator that produces random UUIDs by delegating to uuid.uuid4().

    Used internally when no specific mocking is configured but the patching
    infrastructure is still needed (e.g., for the ignore list feature).
    This generator calls the original uuid.uuid4() function via the proxy.
    """

    def __init__(self) -> None:
        pass  # No state needed - uses get_original() at call time

    def __call__(self) -> uuid.UUID:
        from pytest_uuid._proxy import get_original

        return get_original("uuid4")()

    def reset(self) -> None:
        pass  # No state to reset


class RandomUUID1Generator(UUIDGenerator):
    """Generator that produces UUIDs by delegating to uuid.uuid1().

    Used internally when no specific mocking is configured but the patching
    infrastructure is still needed. Supports optional node and clock_seq
    parameters.

    Args:
        node: The hardware address (48-bit integer). If None, uses system MAC.
        clock_seq: The clock sequence (14-bit integer). If None, uses random.
    """

    def __init__(
        self,
        node: int | None = None,
        clock_seq: int | None = None,
    ) -> None:
        self._node = node
        self._clock_seq = clock_seq

    def __call__(self) -> uuid.UUID:
        from pytest_uuid._proxy import get_original

        return get_original("uuid1")(node=self._node, clock_seq=self._clock_seq)

    def reset(self) -> None:
        pass  # No state to reset


class RandomUUID6Generator(UUIDGenerator):
    """Generator that produces UUIDs by delegating to uuid.uuid6().

    Used internally when no specific mocking is configured. Requires
    Python 3.14+ or the uuid6 backport package.

    Args:
        node: The hardware address (48-bit integer). If None, uses system MAC.
        clock_seq: The clock sequence (14-bit integer). If None, uses random.
    """

    def __init__(
        self,
        node: int | None = None,
        clock_seq: int | None = None,
    ) -> None:
        self._node = node
        self._clock_seq = clock_seq

    def __call__(self) -> uuid.UUID:
        from pytest_uuid._compat import require_uuid6_7_8
        from pytest_uuid._proxy import get_original

        require_uuid6_7_8("uuid6")
        return get_original("uuid6")(node=self._node, clock_seq=self._clock_seq)

    def reset(self) -> None:
        pass  # No state to reset


class RandomUUID7Generator(UUIDGenerator):
    """Generator that produces UUIDs by delegating to uuid.uuid7().

    Used internally when no specific mocking is configured. Requires
    Python 3.14+ or the uuid6 backport package.

    uuid7() uses Unix timestamp (milliseconds) with a monotonic counter
    for sub-millisecond ordering.
    """

    def __init__(self) -> None:
        pass  # No configuration - uuid7 takes no parameters

    def __call__(self) -> uuid.UUID:
        from pytest_uuid._compat import require_uuid6_7_8
        from pytest_uuid._proxy import get_original

        require_uuid6_7_8("uuid7")
        return get_original("uuid7")()

    def reset(self) -> None:
        pass  # No state to reset


class RandomUUID8Generator(UUIDGenerator):
    """Generator that produces UUIDs by delegating to uuid.uuid8().

    Used internally when no specific mocking is configured. Requires
    Python 3.14+ or the uuid6 backport package.

    uuid8() provides a format for experimental or vendor-specific UUIDs.
    """

    def __init__(self) -> None:
        pass  # No configuration - uuid8 generates random custom UUIDs

    def __call__(self) -> uuid.UUID:
        from pytest_uuid._compat import require_uuid6_7_8
        from pytest_uuid._proxy import get_original

        require_uuid6_7_8("uuid8")
        return get_original("uuid8")()

    def reset(self) -> None:
        pass  # No state to reset


# =============================================================================
# Version-specific seeded generators
# =============================================================================


def generate_uuid1_from_random(
    rng: random.Random,
    node: int | None = None,
    clock_seq: int | None = None,
) -> uuid.UUID:
    """Generate a valid UUID v1 using a seeded Random instance.

    The generated UUID has the correct version (1) and variant bits,
    with time fields and node/clock_seq derived from the random source.

    Args:
        rng: A random.Random instance (can be seeded for reproducibility)
        node: Optional 48-bit hardware address. If None, generated from rng.
        clock_seq: Optional 14-bit clock sequence. If None, generated from rng.

    Returns:
        A valid UUID v1 object with deterministic content.
    """
    # Generate time: 60 bits for timestamp (100-nanosecond intervals since Oct 15, 1582)
    # We use random bits since we want reproducibility, not actual time
    time_low = rng.getrandbits(32)  # 32 bits
    time_mid = rng.getrandbits(16)  # 16 bits
    time_hi = rng.getrandbits(12)  # 12 bits (4 bits for version)

    # Generate clock_seq: 14 bits (2 bits for variant)
    clock_seq_value = rng.getrandbits(14) if clock_seq is None else clock_seq & 0x3FFF

    # Generate node: 48 bits (MAC address)
    node_value = rng.getrandbits(48) if node is None else node

    # Construct UUID fields with version and variant
    # time_hi_version: 4 bits version (0001 for v1) + 12 bits time_hi
    time_hi_version = (1 << 12) | time_hi

    # clock_seq_hi_variant: 2 bits variant (10 for RFC 4122) + 6 bits clock_seq_hi
    clock_seq_hi = (clock_seq_value >> 8) & 0x3F
    clock_seq_hi_variant = 0x80 | clock_seq_hi  # Set variant bits to 10
    clock_seq_low = clock_seq_value & 0xFF

    return uuid.UUID(
        fields=(
            time_low,
            time_mid,
            time_hi_version,
            clock_seq_hi_variant,
            clock_seq_low,
            node_value,
        )
    )


def generate_uuid6_from_random(
    rng: random.Random,
    node: int | None = None,
    clock_seq: int | None = None,
) -> uuid.UUID:
    """Generate a valid UUID v6 using a seeded Random instance.

    UUID v6 is a reordered version of UUID v1 for better database sorting.
    The time fields are rearranged so the most significant bits come first.

    Args:
        rng: A random.Random instance (can be seeded for reproducibility)
        node: Optional 48-bit hardware address. If None, generated from rng.
        clock_seq: Optional 14-bit clock sequence. If None, generated from rng.

    Returns:
        A valid UUID v6 object with deterministic content.
    """
    # Generate 60 bits for timestamp (arranged differently than v1)
    time_high = rng.getrandbits(32)  # 32 bits - most significant
    time_mid = rng.getrandbits(16)  # 16 bits
    time_low = rng.getrandbits(12)  # 12 bits (with 4 bits for version)

    # Generate clock_seq: 14 bits
    clock_seq_value = rng.getrandbits(14) if clock_seq is None else clock_seq & 0x3FFF

    # Generate node: 48 bits
    node_value = rng.getrandbits(48) if node is None else node

    # Construct the 128-bit UUID
    # Format: time_high (32) | time_mid (16) | version (4) | time_low (12) |
    #         variant (2) | clock_seq (14) | node (48)
    int_val = time_high << 96
    int_val |= time_mid << 80
    int_val |= 6 << 76  # Version 6
    int_val |= time_low << 64
    int_val |= 0x2 << 62  # Variant (10 binary)
    int_val |= clock_seq_value << 48
    int_val |= node_value

    return uuid.UUID(int=int_val)


def generate_uuid7_from_random(rng: random.Random) -> uuid.UUID:
    """Generate a valid UUID v7 using a seeded Random instance.

    UUID v7 uses Unix timestamp (milliseconds) + random data.
    For reproducibility, we generate the timestamp portion from random too.

    Args:
        rng: A random.Random instance (can be seeded for reproducibility)

    Returns:
        A valid UUID v7 object with deterministic content.
    """
    # Generate 48 bits for Unix timestamp in milliseconds
    unix_ts_ms = rng.getrandbits(48)

    # Generate 12 bits for sub-millisecond precision / random
    rand_a = rng.getrandbits(12)

    # Generate 62 bits of random data
    rand_b = rng.getrandbits(62)

    # Construct the 128-bit UUID
    # Format: unix_ts_ms (48) | version (4) | rand_a (12) | variant (2) | rand_b (62)
    int_val = unix_ts_ms << 80
    int_val |= 7 << 76  # Version 7
    int_val |= rand_a << 64
    int_val |= 0x2 << 62  # Variant (10 binary)
    int_val |= rand_b

    return uuid.UUID(int=int_val)


def generate_uuid8_from_random(rng: random.Random) -> uuid.UUID:
    """Generate a valid UUID v8 using a seeded Random instance.

    UUID v8 is for custom/vendor-specific use. All bits except version
    and variant are available for custom data (here we use random).

    Args:
        rng: A random.Random instance (can be seeded for reproducibility)

    Returns:
        A valid UUID v8 object with deterministic content.
    """
    # Generate all the custom bits
    custom_a = rng.getrandbits(48)  # 48 bits
    custom_b = rng.getrandbits(12)  # 12 bits
    custom_c = rng.getrandbits(62)  # 62 bits

    # Construct the 128-bit UUID
    # Format: custom_a (48) | version (4) | custom_b (12) | variant (2) | custom_c (62)
    int_val = custom_a << 80
    int_val |= 8 << 76  # Version 8
    int_val |= custom_b << 64
    int_val |= 0x2 << 62  # Variant (10 binary)
    int_val |= custom_c

    return uuid.UUID(int=int_val)


class SeededUUID1Generator(UUIDGenerator):
    """Generator that produces reproducible UUID v1 values from a seed.

    UUID v1 is time-based with MAC address. For reproducibility, this
    generator uses seeded random for all fields including time.

    Args:
        seed: Either an integer seed or a random.Random instance.
        node: Optional fixed 48-bit node (MAC address).
        clock_seq: Optional fixed 14-bit clock sequence.
    """

    def __init__(
        self,
        seed: int | random.Random,
        node: int | None = None,
        clock_seq: int | None = None,
    ) -> None:
        if isinstance(seed, random.Random):
            self._rng = seed
            self._seed = None
        else:
            self._seed = seed
            self._rng = random.Random(seed)
        self._node = node
        self._clock_seq = clock_seq

    def __call__(self) -> uuid.UUID:
        return generate_uuid1_from_random(self._rng, self._node, self._clock_seq)

    def reset(self) -> None:
        if self._seed is not None:
            self._rng = random.Random(self._seed)

    @property
    def seed(self) -> int | None:
        """The seed value, or None if initialized with a Random instance."""
        return self._seed


class SeededUUID6Generator(UUIDGenerator):
    """Generator that produces reproducible UUID v6 values from a seed.

    UUID v6 is a reordered version of UUID v1 optimized for database indexing.
    For reproducibility, this generator uses seeded random for all fields.

    Args:
        seed: Either an integer seed or a random.Random instance.
        node: Optional fixed 48-bit node (MAC address).
        clock_seq: Optional fixed 14-bit clock sequence.
    """

    def __init__(
        self,
        seed: int | random.Random,
        node: int | None = None,
        clock_seq: int | None = None,
    ) -> None:
        if isinstance(seed, random.Random):
            self._rng = seed
            self._seed = None
        else:
            self._seed = seed
            self._rng = random.Random(seed)
        self._node = node
        self._clock_seq = clock_seq

    def __call__(self) -> uuid.UUID:
        return generate_uuid6_from_random(self._rng, self._node, self._clock_seq)

    def reset(self) -> None:
        if self._seed is not None:
            self._rng = random.Random(self._seed)

    @property
    def seed(self) -> int | None:
        """The seed value, or None if initialized with a Random instance."""
        return self._seed


class SeededUUID7Generator(UUIDGenerator):
    """Generator that produces reproducible UUID v7 values from a seed.

    UUID v7 uses Unix timestamp (milliseconds) + random data. For
    reproducibility, this generator uses seeded random for all fields.

    Args:
        seed: Either an integer seed or a random.Random instance.
    """

    def __init__(self, seed: int | random.Random) -> None:
        if isinstance(seed, random.Random):
            self._rng = seed
            self._seed = None
        else:
            self._seed = seed
            self._rng = random.Random(seed)

    def __call__(self) -> uuid.UUID:
        return generate_uuid7_from_random(self._rng)

    def reset(self) -> None:
        if self._seed is not None:
            self._rng = random.Random(self._seed)

    @property
    def seed(self) -> int | None:
        """The seed value, or None if initialized with a Random instance."""
        return self._seed


class SeededUUID8Generator(UUIDGenerator):
    """Generator that produces reproducible UUID v8 values from a seed.

    UUID v8 is for custom/vendor-specific use. This generator fills all
    custom bits with seeded random data.

    Args:
        seed: Either an integer seed or a random.Random instance.
    """

    def __init__(self, seed: int | random.Random) -> None:
        if isinstance(seed, random.Random):
            self._rng = seed
            self._seed = None
        else:
            self._seed = seed
            self._rng = random.Random(seed)

    def __call__(self) -> uuid.UUID:
        return generate_uuid8_from_random(self._rng)

    def reset(self) -> None:
        if self._seed is not None:
            self._rng = random.Random(self._seed)

    @property
    def seed(self) -> int | None:
        """The seed value, or None if initialized with a Random instance."""
        return self._seed


def get_seeded_generator(
    version: str,
    seed: int | random.Random,
    node: int | None = None,
    clock_seq: int | None = None,
) -> UUIDGenerator:
    """Factory function to create a version-appropriate seeded generator.

    Args:
        version: UUID version string ("uuid1", "uuid4", "uuid6", "uuid7", "uuid8").
        seed: Either an integer seed or a random.Random instance.
        node: Optional 48-bit node for uuid1/uuid6 (ignored for other versions).
        clock_seq: Optional 14-bit clock sequence for uuid1/uuid6.

    Returns:
        A seeded generator for the specified UUID version.

    Raises:
        ValueError: If the version is not supported for seeded generation.
    """
    if version == "uuid1":
        return SeededUUID1Generator(seed, node=node, clock_seq=clock_seq)
    if version == "uuid4":
        return SeededUUIDGenerator(seed)
    if version == "uuid6":
        return SeededUUID6Generator(seed, node=node, clock_seq=clock_seq)
    if version == "uuid7":
        return SeededUUID7Generator(seed)
    if version == "uuid8":
        return SeededUUID8Generator(seed)
    raise ValueError(
        f"Seeded generation not supported for {version}. "
        f"Supported versions: uuid1, uuid4, uuid6, uuid7, uuid8"
    )


def parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    """Parse a string or UUID into a UUID object."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def parse_uuids(values: Sequence[str | uuid.UUID]) -> list[uuid.UUID]:
    """Parse a sequence of strings or UUIDs into UUID objects."""
    return [parse_uuid(v) for v in values]
