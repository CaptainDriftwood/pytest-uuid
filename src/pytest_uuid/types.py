"""Type definitions and protocols for pytest-uuid.

This module provides:
    - UUIDCall: Dataclass for tracking individual UUID call metadata
    - NamespaceUUIDCall: Dataclass for tracking uuid3/uuid5 call metadata
    - UUIDMockerProtocol: Type protocol for the mock_uuid fixture container
    - UUIDVersionMockerProtocol: Base protocol for version-specific mockers
    - UUID4MockerProtocol: Protocol for uuid4 mocker with extra methods
    - TimeBasedUUIDMockerProtocol: Protocol for uuid1/uuid6 mockers
    - NamespaceUUIDSpyProtocol: Protocol for uuid3/uuid5 spies
    - UUIDSpyProtocol: Type protocol for the spy_uuid fixture

These protocols enable proper type checking and IDE autocomplete when using
the fixtures. Import them for type annotations:

    from pytest_uuid import UUIDMockerProtocol, UUIDSpyProtocol

    def test_example(mock_uuid: UUIDMockerProtocol) -> None:
        mock_uuid.uuid4.set("...")  # IDE autocomplete works here
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
    """Record of a single UUID function call.

    This dataclass captures metadata about each UUID generation call,
    enabling detailed inspection of which calls were mocked vs real
    and which modules made the calls.

    Attributes:
        uuid: The UUID that was returned.
        was_mocked: True if a mocked/generated UUID was returned,
                   False if the real UUID function was called (e.g., ignored module).
        uuid_version: The UUID version (1, 3, 4, 5, 6, 7, or 8). Defaults to 4
                     for backward compatibility.
        caller_module: The __name__ of the module that called the function, or None.
        caller_file: The file path where the call originated, or None.
        caller_line: The line number where the function was called, or None.
        caller_function: The name of the function that made the call, or None.
        caller_qualname: The qualified name of the function (e.g., "MyClass.method"),
                        or None. On Python 3.11+, uses native co_qualname. On earlier
                        versions, uses best-effort reconstruction via self/cls params
                        and gc.get_referrers().

    Example:
        def test_inspect_calls(mock_uuid):
            mock_uuid.set("12345678-1234-4678-8234-567812345678")
            uuid.uuid4()

            call = mock_uuid.calls[0]
            assert call.was_mocked is True
            assert call.uuid_version == 4
            assert call.caller_module == "test_example"
            assert call.caller_function == "test_tracking"
            assert call.caller_qualname == "test_tracking"  # or "MyClass.method"
            assert call.caller_line is not None
    """

    uuid: uuid.UUID
    was_mocked: bool
    uuid_version: int = 4
    caller_module: str | None = None
    caller_file: str | None = None
    caller_line: int | None = None
    caller_function: str | None = None
    caller_qualname: str | None = None


@dataclass(frozen=True)
class NamespaceUUIDCall:
    """Record of a single uuid3() or uuid5() call.

    This dataclass captures metadata about namespace-based UUID generation calls,
    including the namespace and name arguments used to generate the UUID.

    Attributes:
        uuid: The UUID that was returned.
        uuid_version: The UUID version (3 for MD5, 5 for SHA-1).
        namespace: The namespace UUID used for generation.
        name: The name string used for generation.
        caller_module: The __name__ of the module that called the function, or None.
        caller_file: The file path where the call originated, or None.
        caller_line: The line number where the function was called, or None.
        caller_function: The name of the function that made the call, or None.
        caller_qualname: The qualified name of the function, or None.

    Example:
        def test_inspect_namespace_calls(mock_uuid):
            # Enable spy mode for uuid5
            mock_uuid.uuid5.spy()
            uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

            call = mock_uuid.uuid5.calls[0]
            assert call.uuid_version == 5
            assert call.namespace == uuid.NAMESPACE_DNS
            assert call.name == "example.com"
    """

    uuid: uuid.UUID
    uuid_version: int
    namespace: uuid.UUID
    name: str
    caller_module: str | None = None
    caller_file: str | None = None
    caller_line: int | None = None
    caller_function: str | None = None
    caller_qualname: str | None = None


@runtime_checkable
class UUIDVersionMockerProtocol(Protocol):
    """Protocol for version-specific UUID mockers (uuid1, uuid4, uuid6, uuid7, uuid8).

    This protocol defines the common interface for all UUID version mockers,
    enabling proper type checking and IDE autocomplete.

    Example:
        def test_with_types(mock_uuid: UUIDMockerProtocol) -> None:
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"
    """

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set one or more UUIDs to return.

        Args:
            *uuids: UUIDs to return in sequence. If multiple are provided,
                   they will cycle by default when exhausted.
        """
        ...

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID generation.

        Args:
            seed: Integer seed or random.Random instance.
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

    def spy(self) -> None:
        """Enable spy mode - track calls but return real UUIDs.

        In spy mode, UUID calls return real values but are still
        tracked via call_count, generated_uuids, and last_uuid properties.
        """
        ...

    def __call__(self) -> uuid.UUID:
        """Generate and return the next UUID."""
        ...

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator, if any."""
        ...

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation."""
        ...

    @property
    def call_count(self) -> int:
        """Get the number of times this UUID function was called."""
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
        """Get detailed metadata for all calls."""
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


@runtime_checkable
class TimeBasedUUIDMockerProtocol(UUIDVersionMockerProtocol, Protocol):
    """Protocol for time-based UUID mockers (uuid1, uuid6).

    Extends UUIDVersionMockerProtocol with node and clock_seq support.
    """

    def set_node(self, node: int) -> None:
        """Set a fixed node (MAC address) for UUID generation.

        Args:
            node: 48-bit integer representing the hardware address.
        """
        ...

    def set_clock_seq(self, clock_seq: int) -> None:
        """Set a fixed clock sequence for UUID generation.

        Args:
            clock_seq: 14-bit integer for the clock sequence.
        """
        ...


@runtime_checkable
class UUID4MockerProtocol(UUIDVersionMockerProtocol, Protocol):
    """Protocol for UUID4 mocker with additional uuid4-specific methods.

    This extends UUIDVersionMockerProtocol with methods specific to uuid4.
    """

    def set_default(self, default_uuid: str | uuid.UUID) -> None:
        """Set a default UUID to return for all calls.

        Args:
            default_uuid: The UUID to always return.
        """
        ...

    def set_seed_from_node(self) -> None:
        """Set the seed from the current test's node ID.

        Raises:
            RuntimeError: If node ID is not available.
        """
        ...

    def set_ignore(self, *module_prefixes: str) -> None:
        """Set modules to ignore when mocking uuid.uuid4().

        Args:
            *module_prefixes: Module name prefixes to exclude from patching.
                             Calls from these modules will return real UUIDs.
        """
        ...


@runtime_checkable
class NamespaceUUIDSpyProtocol(Protocol):
    """Protocol for namespace-based UUID spies (uuid3, uuid5).

    Since uuid3 and uuid5 are deterministic, these only support spy mode.
    """

    @property
    def uuid_version(self) -> int:
        """The UUID version being tracked (3 or 5)."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether call tracking is currently enabled."""
        ...

    def enable(self) -> None:
        """Start tracking calls to this UUID function."""
        ...

    def disable(self) -> None:
        """Stop tracking calls to this UUID function."""
        ...

    def reset(self) -> None:
        """Reset tracking data."""
        ...

    def __call__(self, namespace: uuid.UUID, name: str) -> uuid.UUID:
        """Track the call and return the real UUID."""
        ...

    @property
    def call_count(self) -> int:
        """Get the number of calls tracked."""
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
    def calls(self) -> list[NamespaceUUIDCall]:
        """Get detailed metadata for all calls."""
        ...

    def calls_from(self, module_prefix: str) -> list[NamespaceUUIDCall]:
        """Get calls from modules matching the given prefix."""
        ...


@runtime_checkable
class UUIDMockerProtocol(Protocol):
    """Protocol for the mock_uuid fixture container.

    This protocol defines the interface for the `mock_uuid` fixture,
    which provides access to version-specific mockers via properties.

    Example:
        def test_with_types(mock_uuid: UUIDMockerProtocol) -> None:
            # Mock uuid4
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"

            # Mock uuid1
            mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")

            # Spy on uuid5 (deterministic, spy-only)
            result = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")
            assert mock_uuid.uuid5.call_count == 1
    """

    @property
    def uuid1(self) -> TimeBasedUUIDMockerProtocol:
        """Access UUID1 mocker API."""
        ...

    @property
    def uuid3(self) -> NamespaceUUIDSpyProtocol:
        """Access UUID3 spy API (spy-only, deterministic)."""
        ...

    @property
    def uuid4(self) -> UUID4MockerProtocol:
        """Access UUID4 mocker API."""
        ...

    @property
    def uuid5(self) -> NamespaceUUIDSpyProtocol:
        """Access UUID5 spy API (spy-only, deterministic)."""
        ...

    @property
    def uuid6(self) -> TimeBasedUUIDMockerProtocol:
        """Access UUID6 mocker API (requires Python 3.14+ or uuid6 package)."""
        ...

    @property
    def uuid7(self) -> UUIDVersionMockerProtocol:
        """Access UUID7 mocker API (requires Python 3.14+ or uuid6 package)."""
        ...

    @property
    def uuid8(self) -> UUIDVersionMockerProtocol:
        """Access UUID8 mocker API (requires Python 3.14+ or uuid6 package)."""
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
