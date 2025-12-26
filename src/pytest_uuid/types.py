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
