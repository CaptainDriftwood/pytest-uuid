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
        pass  # No state needed - uses get_original_uuid4() at call time

    def __call__(self) -> uuid.UUID:
        from pytest_uuid._proxy import get_original_uuid4

        return get_original_uuid4()()

    def reset(self) -> None:
        pass  # No state to reset


def parse_uuid(value: str | uuid.UUID) -> uuid.UUID:
    """Parse a string or UUID into a UUID object."""
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def parse_uuids(values: Sequence[str | uuid.UUID]) -> list[uuid.UUID]:
    """Parse a sequence of strings or UUIDs into UUID objects."""
    return [parse_uuid(v) for v in values]
