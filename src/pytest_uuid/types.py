"""Type definitions for pytest-uuid.

This module provides Protocol classes for type checking and IDE support.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pytest_uuid.generators import ExhaustionBehavior, UUIDGenerator


@dataclass(frozen=True)
class UUIDCall:
    """Record of a single uuid.uuid4() call.

    This dataclass captures metadata about each UUID generation call,
    enabling detailed inspection of which calls were mocked vs real
    and which modules made the calls.

    Attributes:
        uuid: The UUID that was returned.
        was_mocked: True if a mocked/generated UUID was returned,
                   False if the real uuid.uuid4() was called (e.g., ignored module).
        caller_module: The __name__ of the module that called uuid4(), or None.
        caller_file: The file path where the call originated, or None.

    Example:
        def test_inspect_calls(mock_uuid):
            mock_uuid.set("12345678-1234-5678-1234-567812345678")
            uuid.uuid4()

            call = mock_uuid.calls[0]
            assert call.was_mocked is True
            assert call.caller_module == "test_example"
    """

    uuid: uuid.UUID
    was_mocked: bool
    caller_module: str | None = None
    caller_file: str | None = None


@runtime_checkable
class UUIDMockerProtocol(Protocol):
    """Protocol for UUID mocker fixtures.

    This protocol defines the interface for the `mock_uuid` fixture,
    enabling proper type checking and IDE autocomplete.

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

    def set_ignore(self, *module_prefixes: str) -> None:
        """Set modules to ignore when mocking uuid.uuid4().

        Args:
            *module_prefixes: Module name prefixes to exclude from patching.
                             Calls from these modules will return real UUIDs.
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

    @property
    def calls(self) -> list[UUIDCall]:
        """Get detailed metadata for all uuid4 calls."""
        ...

    @property
    def mocked_calls(self) -> list[UUIDCall]:
        """Get only the calls that returned mocked UUIDs."""
        ...

    @property
    def real_calls(self) -> list[UUIDCall]:
        """Get only the calls that returned real UUIDs (e.g., ignored modules)."""
        ...

    @property
    def mocked_count(self) -> int:
        """Get the number of calls that returned mocked UUIDs."""
        ...

    @property
    def real_count(self) -> int:
        """Get the number of calls that returned real UUIDs."""
        ...

    def calls_from(self, module_prefix: str) -> list[UUIDCall]:
        """Get calls from modules matching the given prefix.

        Args:
            module_prefix: Module name prefix to filter by (e.g., "myapp.models").

        Returns:
            List of UUIDCall records from matching modules.
        """
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

    @property
    def calls(self) -> list[UUIDCall]:
        """Get detailed metadata for all uuid4 calls."""
        ...

    def calls_from(self, module_prefix: str) -> list[UUIDCall]:
        """Get calls from modules matching the given prefix.

        Args:
            module_prefix: Module name prefix to filter by (e.g., "myapp.models").

        Returns:
            List of UUIDCall records from matching modules.
        """
        ...

    def __call__(self) -> uuid.UUID:
        """Generate a real UUID and track it."""
        ...

    def reset(self) -> None:
        """Reset tracking data."""
        ...
