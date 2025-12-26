"""UUID generation strategies for pytest-uuid."""

from __future__ import annotations

import random
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class ExhaustionBehavior(Enum):
    """Behavior when a UUID sequence is exhausted."""

    CYCLE = "cycle"  # Loop back to start
    RANDOM = "random"  # Fall back to random UUIDs
    RAISE = "raise"  # Raise UUIDsExhaustedError


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
    # Set version to 4 (bits 76-79)
    random_bits = (random_bits & ~(0xF << 76)) | (4 << 76)
    # Set variant to RFC 4122 (bits 62-63 = 10)
    random_bits = (random_bits & ~(0x3 << 62)) | (0x2 << 62)
    return uuid.UUID(int=random_bits)


class UUIDGenerator(ABC):
    """Abstract base class for UUID generators."""

    @abstractmethod
    def __call__(self) -> uuid.UUID:
        """Generate the next UUID."""

    @abstractmethod
    def reset(self) -> None:
        """Reset the generator to its initial state."""


class StaticUUIDGenerator(UUIDGenerator):
    """Generator that always returns the same UUID."""

    def __init__(self, value: uuid.UUID) -> None:
        self._value = value

    def __call__(self) -> uuid.UUID:
        return self._value

    def reset(self) -> None:
        pass  # No state to reset


class SequenceUUIDGenerator(UUIDGenerator):
    """Generator that returns UUIDs from a sequence."""

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
        if not self._uuids:
            # Empty sequence - behave like random
            return generate_uuid_from_random(self._fallback_rng)

        if self._index < len(self._uuids):
            result = self._uuids[self._index]
            self._index += 1
            return result

        self._exhausted = True

        if self._on_exhausted == ExhaustionBehavior.CYCLE:
            self._index = 1  # Reset to second element (we return first below)
            return self._uuids[0]
        elif self._on_exhausted == ExhaustionBehavior.RANDOM:
            return generate_uuid_from_random(self._fallback_rng)
        else:  # RAISE
            raise UUIDsExhaustedError(len(self._uuids))

    def reset(self) -> None:
        self._index = 0
        self._exhausted = False

    @property
    def is_exhausted(self) -> bool:
        """Whether the sequence has been fully consumed at least once."""
        return self._exhausted


class SeededUUIDGenerator(UUIDGenerator):
    """Generator that produces reproducible UUIDs from a seed."""

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


class RandomUUIDGenerator(UUIDGenerator):
    """Generator that produces random UUIDs (delegates to uuid.uuid4)."""

    def __init__(self, original_uuid4: callable | None = None) -> None:
        self._original_uuid4 = original_uuid4 or uuid.uuid4

    def __call__(self) -> uuid.UUID:
        return self._original_uuid4()

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
