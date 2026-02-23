"""pytest plugin for mocking uuid.uuid4() calls.

This module provides the pytest integration for pytest-uuid, including:

Fixtures:
    mock_uuid: Main fixture for imperative UUID control. Patches uuid4 globally
        and in all modules that imported it directly. Use when you need to
        change UUID behavior during a test or inspect calls.

    spy_uuid: Spy fixture that tracks uuid4 calls without mocking. Returns
        real random UUIDs while recording call metadata.

    mock_uuid_factory: Factory for creating scoped mockers. Use when you need
        to mock uuid4 in a specific module only.

Marker:
    @pytest.mark.freeze_uuid(...): Declarative marker for freezing UUIDs.
        Processed in pytest_runtest_setup hook. Supports all freeze_uuid
        parameters including seed="node" for per-test reproducible UUIDs.

Classes:
    UUIDMocker: The class backing the mock_uuid fixture. Provides set(),
        set_seed(), set_ignore(), and call tracking.

    UUIDSpy: The class backing the spy_uuid fixture. Tracks calls to uuid4
        without replacing them.

Lifecycle:
    - pytest_configure: Registers marker and loads pyproject.toml config
    - pytest_runtest_setup: Activates freeze_uuid marker if present
    - pytest_runtest_teardown: Cleans up freeze_uuid marker
    - pytest_unconfigure: Clears config state

Thread Safety:
    The fixtures are NOT thread-safe. For multi-threaded tests, use
    separate fixtures per thread or synchronize access.
"""

from __future__ import annotations

import inspect
import random
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from pytest_uuid._proxy import (
    GeneratorToken,
    get_current_generator,
    get_original,
    get_original_uuid4,
    install_proxy,
    reset_generator,
    set_generator,
)
from pytest_uuid._tracking import (
    CallTrackingMixin,
    _get_caller_info,
    _get_node_seed,
)
from pytest_uuid.api import UUIDFreezer, _should_ignore_frame
from pytest_uuid.config import (
    PytestUUIDConfig,
    _clear_active_pytest_config,
    _config_key,
    _has_stash,
    _set_active_pytest_config,
    get_config,
    load_config_from_pyproject,
)
from pytest_uuid.generators import (
    ExhaustionBehavior,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDGenerator,
    parse_uuid,
    parse_uuids,
)
from pytest_uuid.types import NamespaceUUIDCall, UUIDCall

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager


class UUIDMocker(CallTrackingMixin):
    """A class to manage mocked UUID values.

    This class provides imperative control over uuid.uuid4() during tests.
    It backs the mock_uuid fixture and supports multiple mocking strategies:
    - Static UUIDs: set("uuid") returns the same UUID every time
    - Sequences: set("uuid1", "uuid2") cycles through UUIDs
    - Seeded: set_seed(42) produces reproducible UUIDs
    - Node-seeded: set_seed_from_node() uses test name as seed

    Call Tracking (inherited from CallTrackingMixin):
        - call_count: Number of uuid4() calls
        - generated_uuids: List of all returned UUIDs
        - last_uuid: Most recent UUID returned
        - calls: List of UUIDCall with metadata (was_mocked, caller_module)
        - mocked_calls / real_calls: Filtered by mock status

    State Management:
        - When no generator is set, returns real random UUIDs
        - reset() clears the generator and tracking data
        - spy() switches to spy mode (track but don't mock)

    Example:
        def test_user_creation(mock_uuid):
            # Set up mocking
            mock_uuid.set("12345678-1234-4678-8234-567812345678")

            # Code under test
            user = create_user()

            # Verify
            assert user.id == "12345678-1234-4678-8234-567812345678"
            assert mock_uuid.call_count == 1

    See Also:
        - mock_uuid fixture: Creates and patches a UUIDMocker automatically
        - freeze_uuid: Decorator/context manager alternative
    """

    def __init__(
        self,
        node_id: str | None = None,
        ignore: list[str] | None = None,
        ignore_defaults: bool = True,
        delegate_to: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._delegate_to = (
            delegate_to  # Generator to delegate to when no local generator
        )
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

        # Ignore list handling
        config = get_config()
        self._ignore_extra = tuple(ignore) if ignore else ()
        self._ignore_defaults = ignore_defaults
        if ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

        # Sub-mockers for other UUID versions (lazily initialized)
        self._uuid1_mocker: UUID1Mocker | None = None
        self._uuid1_token: GeneratorToken | None = None
        self._uuid3_spy: NamespaceUUIDSpy | None = None
        self._uuid3_token: GeneratorToken | None = None
        self._uuid5_spy: NamespaceUUIDSpy | None = None
        self._uuid5_token: GeneratorToken | None = None
        self._uuid6_mocker: UUID6Mocker | None = None
        self._uuid6_token: GeneratorToken | None = None
        self._uuid7_mocker: UUID7Mocker | None = None
        self._uuid7_token: GeneratorToken | None = None
        self._uuid8_mocker: UUID8Mocker | None = None
        self._uuid8_token: GeneratorToken | None = None

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set the UUID(s) to return.

        Args:
            *uuids: One or more UUIDs (as strings or UUID objects) to return.
                   If multiple UUIDs are provided, they will be returned in
                   sequence. Behavior when exhausted is controlled by
                   on_exhausted (default: cycle).
        """
        uuid_list = parse_uuids(uuids)
        # Only use static generator for single UUID if exhaustion is CYCLE
        # Otherwise, keep sequence behavior for proper exhaustion handling
        if len(uuid_list) == 1 and self._on_exhausted == ExhaustionBehavior.CYCLE:
            self._generator = StaticUUIDGenerator(uuid_list[0])
        elif uuid_list:
            self._generator = SequenceUUIDGenerator(
                uuid_list,
                on_exhausted=self._on_exhausted,
            )
        # else: empty list - generator stays None, will return random UUIDs

    def set_default(self, default_uuid: str | uuid.UUID) -> None:
        """Set a default UUID to return for all calls.

        Args:
            default_uuid: The UUID to use as default.
        """
        self._generator = StaticUUIDGenerator(parse_uuid(default_uuid))

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID generation.

        Args:
            seed: Either an integer seed (creates a fresh Random instance)
                  or a random.Random instance (BYOP - bring your own randomizer).
        """
        self._generator = SeededUUIDGenerator(seed)

    def set_seed_from_node(self) -> None:
        """Set the seed from the current test's node ID.

        This generates reproducible UUIDs based on the test's fully qualified
        name. The same test always gets the same sequence of UUIDs.

        Raises:
            RuntimeError: If the node ID is not available.
        """
        if self._node_id is None:
            raise RuntimeError(
                "Node ID not available. This method requires the fixture "
                "to have access to the pytest request object."
            )
        seed = _get_node_seed(self._node_id)
        self._generator = SeededUUIDGenerator(seed)

    def set_exhaustion_behavior(
        self,
        behavior: ExhaustionBehavior | str,
    ) -> None:
        """Set the behavior when a UUID sequence is exhausted.

        Args:
            behavior: One of "cycle", "random", or "raise".
        """
        if isinstance(behavior, str):
            self._on_exhausted = ExhaustionBehavior(behavior)
        else:
            self._on_exhausted = behavior

        if isinstance(self._generator, SequenceUUIDGenerator):
            self._generator._on_exhausted = self._on_exhausted

    def set_ignore(self, *module_prefixes: str) -> None:
        """Set modules to ignore when mocking uuid.uuid4().

        Args:
            *module_prefixes: Module name prefixes to exclude from patching.
                             Calls from these modules will return real UUIDs.

        Example:
            def test_something(mock_uuid):
                mock_uuid.set("12345678-1234-4678-8234-567812345678")
                mock_uuid.set_ignore("sqlalchemy", "celery")
                # uuid4() calls from sqlalchemy or celery will be real
                # Other calls will be mocked
        """
        config = get_config()
        base_ignore = config.get_ignore_list()
        self._ignore_extra = module_prefixes
        self._ignore_list = base_ignore + module_prefixes

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._generator = None
        self._reset_tracking()
        # Reset ignore list based on ignore_defaults setting
        config = get_config()
        if self._ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID.

        Returns:
            The next UUID from the generator, or a random UUID if no
            generator is configured.
        """
        # skip_frames=3: _get_caller_info -> __call__ -> _proxy_uuid4 -> caller
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )

        # Check if any frame in the call stack should be ignored
        if self._ignore_list:
            frame = inspect.currentframe()
            try:
                # Skip only this frame (__call__)
                if frame is not None:
                    frame = frame.f_back

                # Check if any caller should be ignored
                while frame is not None:
                    if _should_ignore_frame(frame, self._ignore_list):
                        result = get_original_uuid4()()
                        self._record_call(
                            result,
                            False,
                            caller_module,
                            caller_file,
                            caller_line,
                            caller_function,
                            caller_qualname,
                        )
                        return result
                    frame = frame.f_back
            finally:
                del frame

        if self._generator is not None:
            result = self._generator()
            was_mocked = True
        elif self._delegate_to is not None:
            # Delegate to marker's generator (e.g., from @pytest.mark.freeze_uuid)
            result = self._delegate_to()
            was_mocked = True
        else:
            result = get_original_uuid4()()
            was_mocked = False

        self._record_call(
            result,
            was_mocked,
            caller_module,
            caller_file,
            caller_line,
            caller_function,
            caller_qualname,
        )
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation.

        Returns the actual integer seed being used, including when
        set_seed_from_node() was called (where the seed is derived
        from the test's node ID).

        Returns None if:
        - Not using seeded generation (using static UUIDs or sequences)
        - A random.Random instance was passed to set_seed() (BYOP mode)
        - No generator has been configured yet
        """
        if isinstance(self._generator, SeededUUIDGenerator):
            return self._generator.seed
        return None

    def spy(self) -> None:
        """Enable spy mode - track calls but return real UUIDs.

        In spy mode, uuid4 calls return real random UUIDs but are still
        tracked via call_count, generated_uuids, and last_uuid properties.

        Example:
            def test_something(mock_uuid):
                mock_uuid.spy()  # Switch to spy mode

                result = uuid.uuid4()  # Returns real random UUID

                assert mock_uuid.call_count == 1
                assert mock_uuid.last_uuid == result
        """
        self._generator = None

    @property
    def uuid1(self) -> UUID1Mocker:
        """Access UUID1 mocking API.

        Returns a UUID1Mocker instance for controlling uuid.uuid1() calls.
        The mocker is lazily initialized and registered with the proxy
        on first access.

        Example:
            def test_uuid1(mock_uuid):
                mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")
                result = uuid.uuid1()
                assert str(result) == "12345678-1234-1234-8234-567812345678"
        """
        if self._uuid1_mocker is None:
            self._uuid1_mocker = UUID1Mocker(
                node_id=self._node_id,
                ignore=list(self._ignore_extra) if self._ignore_extra else None,
                ignore_defaults=self._ignore_defaults,
            )
            # Register with the proxy system
            self._uuid1_token = set_generator(self._uuid1_mocker, func_name="uuid1")
        return self._uuid1_mocker

    @property
    def uuid3(self) -> NamespaceUUIDSpy:
        """Access UUID3 spy API.

        Returns a NamespaceUUIDSpy instance for tracking uuid.uuid3() calls.
        Since uuid3 is deterministic (same namespace + name = same UUID),
        only spy functionality is provided.

        Example:
            def test_uuid3_tracking(mock_uuid):
                result = uuid.uuid3(uuid.NAMESPACE_DNS, "example.com")

                assert mock_uuid.uuid3.call_count == 1
                assert mock_uuid.uuid3.calls[0].namespace == uuid.NAMESPACE_DNS
                assert mock_uuid.uuid3.calls[0].name == "example.com"
        """
        if self._uuid3_spy is None:
            self._uuid3_spy = NamespaceUUIDSpy(uuid_version=3)
            self._uuid3_token = set_generator(self._uuid3_spy, func_name="uuid3")
        return self._uuid3_spy

    @property
    def uuid5(self) -> NamespaceUUIDSpy:
        """Access UUID5 spy API.

        Returns a NamespaceUUIDSpy instance for tracking uuid.uuid5() calls.
        Since uuid5 is deterministic (same namespace + name = same UUID),
        only spy functionality is provided.

        Example:
            def test_uuid5_tracking(mock_uuid):
                result = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

                assert mock_uuid.uuid5.call_count == 1
                assert mock_uuid.uuid5.calls[0].namespace == uuid.NAMESPACE_DNS
                assert mock_uuid.uuid5.calls[0].name == "example.com"
        """
        if self._uuid5_spy is None:
            self._uuid5_spy = NamespaceUUIDSpy(uuid_version=5)
            self._uuid5_token = set_generator(self._uuid5_spy, func_name="uuid5")
        return self._uuid5_spy

    @property
    def uuid6(self) -> UUID6Mocker:
        """Access UUID6 mocking API.

        Returns a UUID6Mocker instance for controlling uuid.uuid6() calls.
        Requires Python 3.14+ or the uuid6 backport package.

        UUID6 is a reordered version of UUID1 optimized for database indexing.

        Example:
            def test_uuid6(mock_uuid):
                mock_uuid.uuid6.set("12345678-1234-6234-8234-567812345678")
                result = uuid.uuid6()
                assert str(result) == "12345678-1234-6234-8234-567812345678"
        """
        if self._uuid6_mocker is None:
            self._uuid6_mocker = UUID6Mocker(
                node_id=self._node_id,
                ignore=list(self._ignore_extra) if self._ignore_extra else None,
                ignore_defaults=self._ignore_defaults,
            )
            self._uuid6_token = set_generator(self._uuid6_mocker, func_name="uuid6")
        return self._uuid6_mocker

    @property
    def uuid7(self) -> UUID7Mocker:
        """Access UUID7 mocking API.

        Returns a UUID7Mocker instance for controlling uuid.uuid7() calls.
        Requires Python 3.14+ or the uuid6 backport package.

        UUID7 is a time-based UUID using Unix timestamp (milliseconds) with
        a monotonic counter for sub-millisecond ordering.

        Example:
            def test_uuid7(mock_uuid):
                mock_uuid.uuid7.set("12345678-1234-7234-8234-567812345678")
                result = uuid.uuid7()
                assert str(result) == "12345678-1234-7234-8234-567812345678"
        """
        if self._uuid7_mocker is None:
            self._uuid7_mocker = UUID7Mocker(
                node_id=self._node_id,
                ignore=list(self._ignore_extra) if self._ignore_extra else None,
                ignore_defaults=self._ignore_defaults,
            )
            self._uuid7_token = set_generator(self._uuid7_mocker, func_name="uuid7")
        return self._uuid7_mocker

    @property
    def uuid8(self) -> UUID8Mocker:
        """Access UUID8 mocking API.

        Returns a UUID8Mocker instance for controlling uuid.uuid8() calls.
        Requires Python 3.14+ or the uuid6 backport package.

        UUID8 provides a format for experimental or vendor-specific UUIDs.

        Example:
            def test_uuid8(mock_uuid):
                mock_uuid.uuid8.set("12345678-1234-8234-8234-567812345678")
                result = uuid.uuid8()
                assert str(result) == "12345678-1234-8234-8234-567812345678"
        """
        if self._uuid8_mocker is None:
            self._uuid8_mocker = UUID8Mocker(
                node_id=self._node_id,
                ignore=list(self._ignore_extra) if self._ignore_extra else None,
                ignore_defaults=self._ignore_defaults,
            )
            self._uuid8_token = set_generator(self._uuid8_mocker, func_name="uuid8")
        return self._uuid8_mocker

    def _cleanup_sub_mockers(self) -> None:
        """Clean up any sub-mockers that were initialized."""
        if self._uuid1_token is not None:
            reset_generator(self._uuid1_token)
            self._uuid1_token = None
            self._uuid1_mocker = None
        if self._uuid3_token is not None:
            reset_generator(self._uuid3_token)
            self._uuid3_token = None
            self._uuid3_spy = None
        if self._uuid5_token is not None:
            reset_generator(self._uuid5_token)
            self._uuid5_token = None
            self._uuid5_spy = None
        if self._uuid6_token is not None:
            reset_generator(self._uuid6_token)
            self._uuid6_token = None
            self._uuid6_mocker = None
        if self._uuid7_token is not None:
            reset_generator(self._uuid7_token)
            self._uuid7_token = None
            self._uuid7_mocker = None
        if self._uuid8_token is not None:
            reset_generator(self._uuid8_token)
            self._uuid8_token = None
            self._uuid8_mocker = None


class UUIDSpy(CallTrackingMixin):
    """A class to spy on UUID generation without mocking.

    This class wraps uuid.uuid4() to track calls while still returning
    real random UUIDs. Similar to pytest-mock's spy functionality. It backs
    the spy_uuid fixture.

    Use this when you need to verify that code generates UUIDs but don't need
    to control what UUIDs are generated.

    Call Tracking (inherited from CallTrackingMixin):
        - call_count: Number of uuid4() calls
        - generated_uuids: List of all returned UUIDs (real random UUIDs)
        - last_uuid: Most recent UUID returned
        - calls: List of UUIDCall with metadata (caller_module, caller_file)

    Note:
        All calls tracked by UUIDSpy have was_mocked=False since real UUIDs
        are always returned.

    Example:
        def test_user_creation(spy_uuid):
            user = create_user()  # Internally calls uuid.uuid4()

            assert spy_uuid.call_count == 1
            assert user.id == str(spy_uuid.last_uuid)

    See Also:
        - spy_uuid fixture: Creates and patches a UUIDSpy automatically
        - mock_uuid.spy(): Switches a UUIDMocker to spy mode
    """

    def __init__(self) -> None:
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

    def __call__(self) -> uuid.UUID:
        """Generate a real UUID and track it."""
        # skip_frames=3: _get_caller_info -> __call__ -> _proxy_uuid4 -> caller
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )
        result = get_original_uuid4()()
        self._record_call(
            result,
            was_mocked=False,
            caller_module=caller_module,
            caller_file=caller_file,
            caller_line=caller_line,
            caller_function=caller_function,
            caller_qualname=caller_qualname,
        )
        return result

    def reset(self) -> None:
        """Reset tracking data."""
        self._reset_tracking()


class UUID1Mocker(CallTrackingMixin):
    """A class to manage mocked UUID1 values.

    This class provides imperative control over uuid.uuid1() during tests.
    It's accessed via mock_uuid.uuid1 and supports multiple mocking strategies:
    - Static UUIDs: set("uuid") returns the same UUID every time
    - Sequences: set("uuid1", "uuid2") cycles through UUIDs
    - Seeded: set_seed(42) produces reproducible UUIDs
    - Real with fixed params: set_node() or set_clock_seq() for controlled generation

    Call Tracking (inherited from CallTrackingMixin):
        - call_count: Number of uuid1() calls
        - generated_uuids: List of all returned UUIDs
        - last_uuid: Most recent UUID returned
        - calls: List of UUIDCall with metadata (was_mocked, caller_module)

    Example:
        def test_time_based_uuid(mock_uuid):
            mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")
            result = uuid.uuid1()
            assert str(result) == "12345678-1234-1234-8234-567812345678"
    """

    def __init__(
        self,
        node_id: str | None = None,
        ignore: list[str] | None = None,
        ignore_defaults: bool = True,
    ) -> None:
        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

        # Fixed parameters for uuid1 generation
        self._fixed_node: int | None = None
        self._fixed_clock_seq: int | None = None

        # Ignore list handling
        config = get_config()
        self._ignore_extra = tuple(ignore) if ignore else ()
        self._ignore_defaults = ignore_defaults
        if ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set the UUID(s) to return for uuid1() calls.

        Args:
            *uuids: One or more UUIDs (as strings or UUID objects) to return.
                   If multiple UUIDs are provided, they will be returned in
                   sequence. Behavior when exhausted is controlled by
                   on_exhausted (default: cycle).
        """
        uuid_list = parse_uuids(uuids)
        if len(uuid_list) == 1 and self._on_exhausted == ExhaustionBehavior.CYCLE:
            self._generator = StaticUUIDGenerator(uuid_list[0])
        elif uuid_list:
            self._generator = SequenceUUIDGenerator(
                uuid_list,
                on_exhausted=self._on_exhausted,
            )

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID1 generation.

        Note: This produces reproducible UUIDs but they are generated using
        the seeded random generator, not actual time-based uuid1 values.

        Args:
            seed: Either an integer seed (creates a fresh Random instance)
                  or a random.Random instance (BYOP - bring your own randomizer).
        """
        self._generator = SeededUUIDGenerator(seed)

    def set_node(self, node: int) -> None:
        """Set a fixed node (MAC address) for uuid1 generation.

        When set, real uuid1() calls will use this node value instead of
        the system MAC address. Useful for reproducible time-based UUIDs.

        Args:
            node: 48-bit integer representing the hardware address.
        """
        self._fixed_node = node

    def set_clock_seq(self, clock_seq: int) -> None:
        """Set a fixed clock sequence for uuid1 generation.

        When set, real uuid1() calls will use this clock_seq value.

        Args:
            clock_seq: 14-bit integer for the clock sequence.
        """
        self._fixed_clock_seq = clock_seq

    def set_exhaustion_behavior(
        self,
        behavior: ExhaustionBehavior | str,
    ) -> None:
        """Set the behavior when a UUID sequence is exhausted."""
        if isinstance(behavior, str):
            self._on_exhausted = ExhaustionBehavior(behavior)
        else:
            self._on_exhausted = behavior

        if isinstance(self._generator, SequenceUUIDGenerator):
            self._generator._on_exhausted = self._on_exhausted

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._generator = None
        self._fixed_node = None
        self._fixed_clock_seq = None
        self._reset_tracking()

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID1.

        Returns:
            The next UUID from the generator, or a real uuid1 if no
            generator is configured (using any fixed node/clock_seq).
        """
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )

        # Check if any frame in the call stack should be ignored
        if self._ignore_list:
            frame = inspect.currentframe()
            try:
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    if _should_ignore_frame(frame, self._ignore_list):
                        result = get_original("uuid1")(
                            node=self._fixed_node, clock_seq=self._fixed_clock_seq
                        )
                        self._record_call(
                            result,
                            False,
                            caller_module,
                            caller_file,
                            caller_line,
                            caller_function,
                            caller_qualname,
                            uuid_version=1,
                        )
                        return result
                    frame = frame.f_back
            finally:
                del frame

        if self._generator is not None:
            result = self._generator()
            was_mocked = True
        else:
            # Use real uuid1 with any fixed parameters
            result = get_original("uuid1")(
                node=self._fixed_node, clock_seq=self._fixed_clock_seq
            )
            was_mocked = False

        self._record_call(
            result,
            was_mocked,
            caller_module,
            caller_file,
            caller_line,
            caller_function,
            caller_qualname,
            uuid_version=1,
        )
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation."""
        if isinstance(self._generator, SeededUUIDGenerator):
            return self._generator.seed
        return None

    def spy(self) -> None:
        """Enable spy mode - track calls but return real uuid1 values."""
        self._generator = None


class UUID6Mocker(CallTrackingMixin):
    """A class to manage mocked UUID6 values.

    This class provides imperative control over uuid.uuid6() during tests.
    Requires Python 3.14+ or the uuid6 backport package.

    UUID6 is a reordered version of UUID1 optimized for database indexing.
    It's accessed via mock_uuid.uuid6 and supports the same mocking strategies
    as UUID1Mocker.

    Example:
        def test_uuid6(mock_uuid):
            mock_uuid.uuid6.set("12345678-1234-6234-8234-567812345678")
            result = uuid.uuid6()
            assert str(result) == "12345678-1234-6234-8234-567812345678"
    """

    def __init__(
        self,
        node_id: str | None = None,
        ignore: list[str] | None = None,
        ignore_defaults: bool = True,
    ) -> None:
        from pytest_uuid._compat import require_uuid6_7_8

        require_uuid6_7_8("uuid6")

        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

        # Fixed parameters for uuid6 generation
        self._fixed_node: int | None = None
        self._fixed_clock_seq: int | None = None

        # Ignore list handling
        config = get_config()
        self._ignore_extra = tuple(ignore) if ignore else ()
        self._ignore_defaults = ignore_defaults
        if ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set the UUID(s) to return for uuid6() calls."""
        uuid_list = parse_uuids(uuids)
        if len(uuid_list) == 1 and self._on_exhausted == ExhaustionBehavior.CYCLE:
            self._generator = StaticUUIDGenerator(uuid_list[0])
        elif uuid_list:
            self._generator = SequenceUUIDGenerator(
                uuid_list,
                on_exhausted=self._on_exhausted,
            )

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID6 generation."""
        self._generator = SeededUUIDGenerator(seed)

    def set_node(self, node: int) -> None:
        """Set a fixed node (MAC address) for uuid6 generation."""
        self._fixed_node = node

    def set_clock_seq(self, clock_seq: int) -> None:
        """Set a fixed clock sequence for uuid6 generation."""
        self._fixed_clock_seq = clock_seq

    def set_exhaustion_behavior(self, behavior: ExhaustionBehavior | str) -> None:
        """Set the behavior when a UUID sequence is exhausted."""
        if isinstance(behavior, str):
            self._on_exhausted = ExhaustionBehavior(behavior)
        else:
            self._on_exhausted = behavior
        if isinstance(self._generator, SequenceUUIDGenerator):
            self._generator._on_exhausted = self._on_exhausted

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._generator = None
        self._fixed_node = None
        self._fixed_clock_seq = None
        self._reset_tracking()

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID6."""
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )

        if self._ignore_list:
            frame = inspect.currentframe()
            try:
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    if _should_ignore_frame(frame, self._ignore_list):
                        result = get_original("uuid6")(
                            node=self._fixed_node, clock_seq=self._fixed_clock_seq
                        )
                        self._record_call(
                            result,
                            False,
                            caller_module,
                            caller_file,
                            caller_line,
                            caller_function,
                            caller_qualname,
                            uuid_version=6,
                        )
                        return result
                    frame = frame.f_back
            finally:
                del frame

        if self._generator is not None:
            result = self._generator()
            was_mocked = True
        else:
            result = get_original("uuid6")(
                node=self._fixed_node, clock_seq=self._fixed_clock_seq
            )
            was_mocked = False

        self._record_call(
            result,
            was_mocked,
            caller_module,
            caller_file,
            caller_line,
            caller_function,
            caller_qualname,
            uuid_version=6,
        )
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation."""
        if isinstance(self._generator, SeededUUIDGenerator):
            return self._generator.seed
        return None

    def spy(self) -> None:
        """Enable spy mode - track calls but return real uuid6 values."""
        self._generator = None


class UUID7Mocker(CallTrackingMixin):
    """A class to manage mocked UUID7 values.

    This class provides imperative control over uuid.uuid7() during tests.
    Requires Python 3.14+ or the uuid6 backport package.

    UUID7 is a time-based UUID using Unix timestamp (milliseconds) with
    a monotonic counter for sub-millisecond ordering.

    Example:
        def test_uuid7(mock_uuid):
            mock_uuid.uuid7.set("12345678-1234-7234-8234-567812345678")
            result = uuid.uuid7()
            assert str(result) == "12345678-1234-7234-8234-567812345678"
    """

    def __init__(
        self,
        node_id: str | None = None,
        ignore: list[str] | None = None,
        ignore_defaults: bool = True,
    ) -> None:
        from pytest_uuid._compat import require_uuid6_7_8

        require_uuid6_7_8("uuid7")

        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

        # Ignore list handling
        config = get_config()
        self._ignore_extra = tuple(ignore) if ignore else ()
        self._ignore_defaults = ignore_defaults
        if ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set the UUID(s) to return for uuid7() calls."""
        uuid_list = parse_uuids(uuids)
        if len(uuid_list) == 1 and self._on_exhausted == ExhaustionBehavior.CYCLE:
            self._generator = StaticUUIDGenerator(uuid_list[0])
        elif uuid_list:
            self._generator = SequenceUUIDGenerator(
                uuid_list,
                on_exhausted=self._on_exhausted,
            )

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID7 generation."""
        self._generator = SeededUUIDGenerator(seed)

    def set_exhaustion_behavior(self, behavior: ExhaustionBehavior | str) -> None:
        """Set the behavior when a UUID sequence is exhausted."""
        if isinstance(behavior, str):
            self._on_exhausted = ExhaustionBehavior(behavior)
        else:
            self._on_exhausted = behavior
        if isinstance(self._generator, SequenceUUIDGenerator):
            self._generator._on_exhausted = self._on_exhausted

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._generator = None
        self._reset_tracking()

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID7."""
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )

        if self._ignore_list:
            frame = inspect.currentframe()
            try:
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    if _should_ignore_frame(frame, self._ignore_list):
                        result = get_original("uuid7")()
                        self._record_call(
                            result,
                            False,
                            caller_module,
                            caller_file,
                            caller_line,
                            caller_function,
                            caller_qualname,
                            uuid_version=7,
                        )
                        return result
                    frame = frame.f_back
            finally:
                del frame

        if self._generator is not None:
            result = self._generator()
            was_mocked = True
        else:
            result = get_original("uuid7")()
            was_mocked = False

        self._record_call(
            result,
            was_mocked,
            caller_module,
            caller_file,
            caller_line,
            caller_function,
            caller_qualname,
            uuid_version=7,
        )
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation."""
        if isinstance(self._generator, SeededUUIDGenerator):
            return self._generator.seed
        return None

    def spy(self) -> None:
        """Enable spy mode - track calls but return real uuid7 values."""
        self._generator = None


class UUID8Mocker(CallTrackingMixin):
    """A class to manage mocked UUID8 values.

    This class provides imperative control over uuid.uuid8() during tests.
    Requires Python 3.14+ or the uuid6 backport package.

    UUID8 provides a format for experimental or vendor-specific UUIDs
    with custom pseudo-random data in three fields.

    Example:
        def test_uuid8(mock_uuid):
            mock_uuid.uuid8.set("12345678-1234-8234-8234-567812345678")
            result = uuid.uuid8()
            assert str(result) == "12345678-1234-8234-8234-567812345678"
    """

    def __init__(
        self,
        node_id: str | None = None,
        ignore: list[str] | None = None,
        ignore_defaults: bool = True,
    ) -> None:
        from pytest_uuid._compat import require_uuid6_7_8

        require_uuid6_7_8("uuid8")

        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

        # Ignore list handling
        config = get_config()
        self._ignore_extra = tuple(ignore) if ignore else ()
        self._ignore_defaults = ignore_defaults
        if ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set the UUID(s) to return for uuid8() calls."""
        uuid_list = parse_uuids(uuids)
        if len(uuid_list) == 1 and self._on_exhausted == ExhaustionBehavior.CYCLE:
            self._generator = StaticUUIDGenerator(uuid_list[0])
        elif uuid_list:
            self._generator = SequenceUUIDGenerator(
                uuid_list,
                on_exhausted=self._on_exhausted,
            )

    def set_seed(self, seed: int | random.Random) -> None:
        """Set a seed for reproducible UUID8 generation."""
        self._generator = SeededUUIDGenerator(seed)

    def set_exhaustion_behavior(self, behavior: ExhaustionBehavior | str) -> None:
        """Set the behavior when a UUID sequence is exhausted."""
        if isinstance(behavior, str):
            self._on_exhausted = ExhaustionBehavior(behavior)
        else:
            self._on_exhausted = behavior
        if isinstance(self._generator, SequenceUUIDGenerator):
            self._generator._on_exhausted = self._on_exhausted

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._generator = None
        self._reset_tracking()

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID8."""
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )

        if self._ignore_list:
            frame = inspect.currentframe()
            try:
                if frame is not None:
                    frame = frame.f_back
                while frame is not None:
                    if _should_ignore_frame(frame, self._ignore_list):
                        result = get_original("uuid8")()
                        self._record_call(
                            result,
                            False,
                            caller_module,
                            caller_file,
                            caller_line,
                            caller_function,
                            caller_qualname,
                            uuid_version=8,
                        )
                        return result
                    frame = frame.f_back
            finally:
                del frame

        if self._generator is not None:
            result = self._generator()
            was_mocked = True
        else:
            result = get_original("uuid8")()
            was_mocked = False

        self._record_call(
            result,
            was_mocked,
            caller_module,
            caller_file,
            caller_line,
            caller_function,
            caller_qualname,
            uuid_version=8,
        )
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation."""
        if isinstance(self._generator, SeededUUIDGenerator):
            return self._generator.seed
        return None

    def spy(self) -> None:
        """Enable spy mode - track calls but return real uuid8 values."""
        self._generator = None


class NamespaceUUIDSpy:
    """A class to spy on uuid3() or uuid5() calls.

    Since uuid3 and uuid5 are deterministic (same inputs = same output),
    this class only provides spy functionality - it tracks calls with their
    namespace and name arguments without modifying the output.

    Attributes:
        uuid_version: The UUID version being tracked (3 or 5).
        call_count: Number of calls tracked.
        calls: List of NamespaceUUIDCall records with full metadata.

    Example:
        def test_uuid5_tracking(mock_uuid):
            mock_uuid.uuid5.enable()
            result = uuid.uuid5(uuid.NAMESPACE_DNS, "example.com")

            assert mock_uuid.uuid5.call_count == 1
            assert mock_uuid.uuid5.calls[0].namespace == uuid.NAMESPACE_DNS
            assert mock_uuid.uuid5.calls[0].name == "example.com"
    """

    def __init__(self, uuid_version: int) -> None:
        if uuid_version not in (3, 5):
            raise ValueError(
                "NamespaceUUIDSpy only supports uuid3 (version=3) or uuid5 (version=5)"
            )
        self._uuid_version = uuid_version
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[NamespaceUUIDCall] = []
        self._enabled: bool = False

    def enable(self) -> None:
        """Start tracking calls to this UUID function."""
        self._enabled = True

    def disable(self) -> None:
        """Stop tracking calls to this UUID function."""
        self._enabled = False

    def reset(self) -> None:
        """Reset tracking data."""
        self._call_count = 0
        self._generated_uuids.clear()
        self._calls.clear()

    def __call__(self, namespace: uuid.UUID, name: str) -> uuid.UUID:
        """Track the call and return the real UUID.

        Args:
            namespace: The namespace UUID.
            name: The name to hash with the namespace.

        Returns:
            The real uuid3 or uuid5 result.
        """
        # Get caller info
        caller_module, caller_file, caller_line, caller_function, caller_qualname = (
            _get_caller_info(skip_frames=3)
        )

        # Call the original function
        func_name = f"uuid{self._uuid_version}"
        result = get_original(func_name)(namespace, name)

        # Record the call
        self._call_count += 1
        self._generated_uuids.append(result)
        self._calls.append(
            NamespaceUUIDCall(
                uuid=result,
                uuid_version=self._uuid_version,
                namespace=namespace,
                name=name,
                caller_module=caller_module,
                caller_file=caller_file,
                caller_line=caller_line,
                caller_function=caller_function,
                caller_qualname=caller_qualname,
            )
        )

        return result

    @property
    def uuid_version(self) -> int:
        """The UUID version being tracked (3 or 5)."""
        return self._uuid_version

    @property
    def call_count(self) -> int:
        """Get the number of calls tracked."""
        return self._call_count

    @property
    def generated_uuids(self) -> list[uuid.UUID]:
        """Get a list of all UUIDs that have been generated."""
        return list(self._generated_uuids)

    @property
    def last_uuid(self) -> uuid.UUID | None:
        """Get the most recently generated UUID, or None if none generated."""
        return self._generated_uuids[-1] if self._generated_uuids else None

    @property
    def calls(self) -> list[NamespaceUUIDCall]:
        """Get detailed metadata for all calls."""
        return list(self._calls)

    def calls_from(self, module_prefix: str) -> list[NamespaceUUIDCall]:
        """Get calls from modules matching the given prefix.

        Args:
            module_prefix: Module name prefix to filter by.

        Returns:
            List of NamespaceUUIDCall records from matching modules.
        """
        return [
            c
            for c in self._calls
            if c.caller_module and c.caller_module.startswith(module_prefix)
        ]

    def calls_with_namespace(self, namespace: uuid.UUID) -> list[NamespaceUUIDCall]:
        """Get calls that used a specific namespace.

        Args:
            namespace: The namespace UUID to filter by.

        Returns:
            List of NamespaceUUIDCall records using that namespace.
        """
        return [c for c in self._calls if c.namespace == namespace]

    def calls_with_name(self, name: str) -> list[NamespaceUUIDCall]:
        """Get calls that used a specific name.

        Args:
            name: The name to filter by.

        Returns:
            List of NamespaceUUIDCall records using that name.
        """
        return [c for c in self._calls if c.name == name]


def pytest_load_initial_conftests(
    early_config: pytest.Config,
    parser: pytest.Parser,  # noqa: ARG001
    args: list[str],  # noqa: ARG001
) -> None:
    """Install the uuid4 proxy BEFORE conftest files are loaded.

    This is critical: conftest files may import modules that do
    `from uuid import uuid4`, and we need our proxy installed first
    so those imports capture the proxy, not the original function.

    pytest hook order for reference:
    1. pytest_load_initial_conftests (proxy installed here)
    2. conftest.py files are loaded
    3. pytest_configure (config setup here)
    """
    install_proxy()
    # Also set early config so freeze_uuid can access it during conftest loading
    _set_active_pytest_config(early_config)


def pytest_configure(config: pytest.Config) -> None:
    """Load config from pyproject.toml and register the freeze_uuid marker."""
    from pathlib import Path

    # Update active config (early_config may have been replaced)
    _set_active_pytest_config(config)

    # Set active pytest config (enables get_config() to work)
    _set_active_pytest_config(config)

    # Initialize stash with default config
    if _has_stash and _config_key is not None and hasattr(config, "stash"):
        config.stash[_config_key] = PytestUUIDConfig()

    # Load configuration from pyproject.toml (updates stash via configure())
    load_config_from_pyproject(Path(config.rootdir))  # type: ignore[unresolved-attribute]

    config.addinivalue_line(
        "markers",
        "freeze_uuid(uuids=None, *, seed=None, on_exhausted=None, ignore=None, "
        "ignore_defaults=True): "
        "Freeze uuid.uuid4() for this test. "
        "uuids: static UUID(s) to return. "
        "seed: int, random.Random, or 'node' for reproducible generation. "
        "on_exhausted: 'cycle', 'random', or 'raise' when sequence exhausted. "
        "ignore: module prefixes to exclude from patching. "
        "ignore_defaults: whether to include default ignore list (default True).",
    )


def pytest_unconfigure(config: pytest.Config) -> None:  # noqa: ARG001
    """Clean up when pytest exits."""
    _clear_active_pytest_config()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Handle freeze_uuid markers on tests."""
    marker = item.get_closest_marker("freeze_uuid")
    if marker is None:
        return

    args = marker.args
    kwargs = dict(marker.kwargs)

    uuids = args[0] if args else kwargs.pop("uuids", None)

    seed = kwargs.get("seed")
    if seed == "node":
        kwargs["node_id"] = item.nodeid

    freezer = UUIDFreezer(uuids=uuids, **kwargs)
    freezer.__enter__()

    item._uuid_freezer = freezer  # type: ignore[attr-defined]


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> None:
    """Clean up freeze_uuid markers."""
    freezer = getattr(item, "_uuid_freezer", None)
    if freezer is not None:
        freezer.__exit__(None, None, None)
        delattr(item, "_uuid_freezer")


@pytest.fixture
def mock_uuid(
    request: pytest.FixtureRequest,
) -> Iterator[UUIDMocker]:
    """Fixture that provides a UUIDMocker for controlling uuid.uuid4() calls.

    This fixture uses the proxy system to intercept all uuid.uuid4() calls,
    including those captured at import time (e.g., Pydantic default_factory).

    Example:
        def test_something(mock_uuid):
            mock_uuid.set("12345678-1234-4678-8234-567812345678")
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"

        def test_multiple_uuids(mock_uuid):
            mock_uuid.set(
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
            )
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
            assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
            # Cycles back to the first UUID
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

        def test_seeded(mock_uuid):
            mock_uuid.set_seed(42)
            # Always produces the same sequence of UUIDs
            first = uuid.uuid4()
            mock_uuid.set_seed(42)  # Reset with same seed
            assert uuid.uuid4() == first

        def test_node_seeded(mock_uuid):
            mock_uuid.set_seed_from_node()
            # Same test always gets the same UUIDs

    Returns:
        UUIDMocker: An object to control the mocked UUIDs.
    """
    # Check for fixture conflict - if another fixture already set a generator
    current = get_current_generator()
    if current is not None and isinstance(current, UUIDSpy):
        raise pytest.UsageError(
            "Cannot use both 'mock_uuid' and 'spy_uuid' fixtures in the same test. "
            "Use mock_uuid.spy() to switch to spy mode instead."
        )

    # Check if marker set a generator that we should delegate to
    marker_freezer = getattr(request.node, "_uuid_freezer", None)
    delegate_to = current if marker_freezer is not None else None

    mocker = UUIDMocker(node_id=request.node.nodeid, delegate_to=delegate_to)
    token = set_generator(mocker)
    yield mocker
    # Clean up sub-mockers first (they were registered after main mocker)
    mocker._cleanup_sub_mockers()
    reset_generator(token)


@pytest.fixture
def mock_uuid_factory() -> Callable[..., AbstractContextManager[UUIDMocker]]:
    """Fixture factory for creating scoped UUIDMocker instances.

    With the proxy-based architecture, all uuid.uuid4() calls go through
    the global proxy. This factory creates a context manager that sets up
    and tears down a UUIDMocker for the duration of the context.

    Note: The module_path parameter is now optional and primarily used for
    documentation/clarity. The proxy affects all uuid4 calls globally.

    Example:
        def test_with_scoped_mock(mock_uuid_factory):
            with mock_uuid_factory() as mocker:
                mocker.set("12345678-1234-4678-8234-567812345678")
                result = create_model()  # Calls uuid4() internally
                assert result.id == "12345678-1234-4678-8234-567812345678"

        def test_mock_default_ignored_package(mock_uuid_factory):
            # Mock packages that are normally ignored (e.g., botocore)
            with mock_uuid_factory(ignore_defaults=False) as mocker:
                mocker.set("12345678-1234-4678-8234-567812345678")
                # botocore will now receive mocked UUIDs

    Args:
        module_path: Optional module path (for documentation/backward compat).
        ignore_defaults: Whether to include default ignore list (default True).
            Set to False to mock all modules including those in DEFAULT_IGNORE_PACKAGES.

    Returns:
        A context manager factory that yields a UUIDMocker.
    """

    @contextmanager
    def factory(
        module_path: str | None = None,
        *,
        ignore_defaults: bool = True,
    ) -> Iterator[UUIDMocker]:
        # module_path is kept for backward compatibility but no longer used
        # with the proxy approach (all uuid4 calls go through the proxy)
        _ = module_path
        mocker = UUIDMocker(ignore_defaults=ignore_defaults)
        token = set_generator(mocker)
        try:
            yield mocker
        finally:
            reset_generator(token)

    return factory


@pytest.fixture
def spy_uuid() -> Iterator[UUIDSpy]:
    """Fixture that spies on uuid.uuid4() calls without mocking.

    This fixture uses the proxy to track all uuid.uuid4() calls while still
    returning real random UUIDs. Use this when you need to verify
    that uuid.uuid4() was called, but don't need to control its output.

    Example:
        def test_something(spy_uuid):
            # Call some code that uses uuid4
            result = uuid.uuid4()

            # Verify uuid4 was called
            assert spy_uuid.call_count == 1
            assert spy_uuid.last_uuid == result

    Returns:
        UUIDSpy: An object to inspect uuid4 calls.
    """
    # Check for fixture conflict - if another fixture already set a generator
    current = get_current_generator()
    if current is not None and isinstance(current, UUIDMocker):
        raise pytest.UsageError(
            "Cannot use both 'mock_uuid' and 'spy_uuid' fixtures in the same test. "
            "Use mock_uuid.spy() to switch to spy mode instead."
        )

    spy = UUIDSpy()
    token = set_generator(spy)
    yield spy
    reset_generator(token)
