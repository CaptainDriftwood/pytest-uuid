"""Type definitions for pytest-uuid.

This module provides Protocol classes for type checking and IDE support.
"""

from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pytest_uuid.generators import ExhaustionBehavior, UUIDGenerator


@runtime_checkable
class UUIDMockerProtocol(Protocol):
    """Protocol for UUID mocker fixtures.

    This protocol defines the interface for `mock_uuid` and `uuid_freezer`
    fixtures, enabling proper type checking and IDE autocomplete.

    Example:
        def test_with_types(mock_uuid: UUIDMockerProtocol) -> None:
            mock_uuid.set("12345678-1234-5678-1234-567812345678")
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-5678-1234-567812345678"
    """

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set one or more UUIDs to return.

        Args:
            *uuids: UUIDs to return in sequence. If multiple are provided,
                   they will cycle by default when exhausted.
        """
        ...

    def set_default(self, default_uuid: str | uuid.UUID) -> None:
        """Set a default UUID to return for all calls.

        Args:
            default_uuid: The UUID to always return.
        """
        ...

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID generation.

        Args:
            seed: Integer seed or random.Random instance.
        """
        ...

    def set_seed_from_node(self) -> None:
        """Set the seed from the current test's node ID.

        Raises:
            RuntimeError: If node ID is not available.
        """
        ...

    def set_exhaustion_behavior(self, behavior: ExhaustionBehavior | str) -> None:
        """Set behavior when UUID sequence is exhausted.

        Args:
            behavior: One of "cycle", "random", or "raise".
        """
        ...

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        ...

    def __call__(self) -> uuid.UUID:
        """Generate and return the next UUID."""
        ...

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator, if any."""
        ...

    @property
    def call_count(self) -> int:
        """Get the number of times uuid4 was called."""
        ...

    @property
    def generated_uuids(self) -> list[uuid.UUID]:
        """Get a list of all UUIDs that have been generated."""
        ...

    @property
    def last_uuid(self) -> uuid.UUID | None:
        """Get the most recently generated UUID, or None if none generated."""
        ...

    def spy(self) -> None:
        """Enable spy mode - track calls but return real UUIDs.

        In spy mode, uuid4 calls return real random UUIDs but are still
        tracked via call_count, generated_uuids, and last_uuid properties.
        """
        ...


@runtime_checkable
class UUIDSpyProtocol(Protocol):
    """Protocol for UUID spy fixtures.

    A spy tracks uuid4 calls without replacing them with mocked values.
    Use this when you need to verify uuid4 was called without controlling output.

    Example:
        def test_with_spy(spy_uuid: UUIDSpyProtocol) -> None:
            result = uuid.uuid4()  # Returns real random UUID
            assert spy_uuid.call_count == 1
            assert spy_uuid.last_uuid == result
    """

    @property
    def call_count(self) -> int:
        """Get the number of times uuid4 was called."""
        ...

    @property
    def generated_uuids(self) -> list[uuid.UUID]:
        """Get a list of all UUIDs that have been generated."""
        ...

    @property
    def last_uuid(self) -> uuid.UUID | None:
        """Get the most recently generated UUID, or None if none generated."""
        ...

    def __call__(self) -> uuid.UUID:
        """Generate a real UUID and track it."""
        ...

    def reset(self) -> None:
        """Reset tracking data."""
        ...
