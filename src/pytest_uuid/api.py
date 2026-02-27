"""Core API for pytest-uuid including the freeze_uuid decorator.

This module provides the primary user-facing API for controlling UUID generation:

    freeze_uuid: Factory function that returns a UUIDFreezer. Use this as a
        decorator (@freeze_uuid("...")) or context manager (with freeze_uuid("...")).
        This is the recommended way to mock UUIDs in a declarative style.

    UUIDFreezer: The underlying class that handles patching. Supports both
        decorator and context manager usage. Most users should use freeze_uuid()
        instead of instantiating UUIDFreezer directly.

How Patching Works:
    When activated, UUIDFreezer patches uuid.uuid4 globally AND scans sys.modules
    to find any module that has imported uuid4 directly (via `from uuid import uuid4`).
    This ensures mocking works regardless of how the code under test imports uuid4.

Thread Safety:
    Both UUID generation and call tracking are thread-safe. Multiple threads can
    safely call uuid.uuid4() etc. while freezers are active. Call tracking uses
    per-instance locks to ensure consistent counting and metadata recording.

    However, each UUIDFreezer instance should only be entered/exited from a single
    thread (don't share a context manager across threads). For multi-threaded tests,
    each thread should use its own freezer.

Example:
    # As a decorator
    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    def test_user_creation():
        user = create_user()
        assert user.id == "12345678-1234-4678-8234-567812345678"

    # As a context manager with call tracking
    with freeze_uuid(seed=42) as freezer:
        first = uuid.uuid4()
        second = uuid.uuid4()
        assert freezer.call_count == 2
        assert freezer.generated_uuids == [first, second]
"""

from __future__ import annotations

import functools
import inspect
import random
import threading
import uuid
from typing import TYPE_CHECKING, Literal, overload

from pytest_uuid._proxy import (
    GeneratorToken,
    get_original,
    reset_generator,
    set_generator,
)
from pytest_uuid._tracking import (
    CallTrackingMixin,
    _get_caller_info,
    _get_node_seed,
)
from pytest_uuid.config import get_config
from pytest_uuid.generators import (
    ExhaustionBehavior,
    RandomUUID1Generator,
    RandomUUID6Generator,
    RandomUUID7Generator,
    RandomUUID8Generator,
    RandomUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDGenerator,
    get_seeded_generator,
    parse_uuid,
    parse_uuids,
)
from pytest_uuid.types import UUIDCall

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

__all__ = [
    "UUIDFreezer",
    "freeze_uuid",
    "freeze_uuid1",
    "freeze_uuid4",
    "freeze_uuid6",
    "freeze_uuid7",
    "freeze_uuid8",
]


def _should_ignore_frame(frame: object, ignore_list: tuple[str, ...]) -> bool:
    """Check if a frame's module should be ignored.

    Args:
        frame: A frame object from the call stack.
        ignore_list: Tuple of module prefixes to ignore.

    Returns:
        True if the frame's module starts with any prefix in ignore_list.
    """
    if not ignore_list:
        return False

    module_name = getattr(frame, "f_globals", {}).get("__name__", "")
    if not module_name:
        return False

    return any(module_name.startswith(prefix) for prefix in ignore_list)


class UUIDFreezer(CallTrackingMixin):
    """Context manager and decorator for freezing UUID function calls.

    This class provides fine-grained control over UUID generation during tests.
    It can be used as a decorator or context manager. Most users should use
    the freeze_uuid4(), freeze_uuid7(), etc. factory functions instead of
    instantiating this directly.

    Usage Patterns:
        - As decorator: @freeze_uuid4("uuid") applies to entire function
        - As context manager: with freeze_uuid4("uuid") as f: ... for scoped control
        - On classes: @freeze_uuid4("uuid") wraps all test_* methods

    Call Tracking:
        While active, tracks all calls to the target UUID function via inherited properties:
        - call_count: Total number of calls
        - generated_uuids: List of all UUIDs returned
        - last_uuid: Most recent UUID returned
        - calls: List of UUIDCall records with metadata
        - mocked_calls / real_calls: Filtered by whether mocked or ignored

    Example:
        # Context manager with call inspection
        with freeze_uuid4(seed=42) as freezer:
            first = uuid.uuid4()
            second = uuid.uuid4()

        assert freezer.call_count == 2
        assert freezer.generated_uuids[0] == first
        for call in freezer.calls:
            print(f"{call.caller_module}: {call.uuid}")
    """

    def __init__(
        self,
        uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
        *,
        uuid_version: str = "uuid4",
        seed: int | random.Random | Literal["node"] | None = None,
        on_exhausted: ExhaustionBehavior | str | None = None,
        ignore: Sequence[str] | None = None,
        ignore_defaults: bool = True,
        node_id: str | None = None,
        node: int | None = None,
        clock_seq: int | None = None,
    ) -> None:
        """Initialize the UUID freezer.

        Args:
            uuids: Static UUID(s) to return. Can be a single UUID or a sequence.
            uuid_version: The UUID function to freeze ("uuid1", "uuid4", "uuid6",
                "uuid7", "uuid8"). Default is "uuid4".
            seed: Seed for reproducible UUID generation. Can be:
                - int: Create a fresh Random instance with this seed
                - random.Random: Use this Random instance directly
                - "node": Derive seed from the pytest node ID (requires node_id)
            on_exhausted: Behavior when UUID sequence is exhausted.
            ignore: Additional module prefixes to ignore (won't be patched).
            ignore_defaults: Whether to include default ignore list (e.g., botocore).
                Set to False to mock all modules including those in DEFAULT_IGNORE_PACKAGES.
            node_id: The pytest node ID (required when seed="node").
            node: Fixed 48-bit node (MAC address) for uuid1/uuid6 seeded generation.
            clock_seq: Fixed 14-bit clock sequence for uuid1/uuid6 seeded generation.
        """
        self._uuids = uuids
        self._uuid_version = uuid_version
        self._seed = seed
        self._node_id = node_id
        self._node = node
        self._clock_seq = clock_seq
        self._ignore_extra = tuple(ignore) if ignore else ()

        config = get_config()
        if on_exhausted is None:
            self._on_exhausted = config.default_exhaustion_behavior
        elif isinstance(on_exhausted, str):
            self._on_exhausted = ExhaustionBehavior(on_exhausted)
        else:
            self._on_exhausted = on_exhausted

        self._ignore_defaults = ignore_defaults
        if ignore_defaults:
            self._ignore_list = config.get_ignore_list() + self._ignore_extra
        else:
            self._ignore_list = self._ignore_extra

        # These are set during __enter__
        self._generator: UUIDGenerator | None = None
        self._token: GeneratorToken | None = None

        # Call tracking
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []
        self._tracking_lock = threading.Lock()

    def _create_generator(self) -> UUIDGenerator:
        """Create the appropriate UUID generator based on configuration."""
        # Seeded mode takes precedence
        if self._seed is not None:
            if self._seed == "node":
                if self._node_id is None:
                    marker_name = f"freeze_{self._uuid_version}"
                    raise ValueError(
                        f"seed='node' requires node_id to be provided. "
                        f"Use @pytest.mark.{marker_name}(seed='node') or pass node_id explicitly."
                    )
                actual_seed: int | random.Random = _get_node_seed(self._node_id)
            else:
                # seed is either an int or random.Random instance
                actual_seed = self._seed

            # Use version-appropriate seeded generator
            return get_seeded_generator(
                self._uuid_version,
                actual_seed,
                node=self._node,
                clock_seq=self._clock_seq,
            )

        if self._uuids is not None:
            if isinstance(self._uuids, (str, uuid.UUID)):
                # Single UUID as string/UUID - use static generator
                return StaticUUIDGenerator(parse_uuid(self._uuids))
            uuid_list = parse_uuids(self._uuids)
            # Only use static generator for single UUID if exhaustion is CYCLE
            # Otherwise, keep sequence behavior for proper exhaustion handling
            if len(uuid_list) == 1 and self._on_exhausted == ExhaustionBehavior.CYCLE:
                return StaticUUIDGenerator(uuid_list[0])
            return SequenceUUIDGenerator(
                uuid_list,
                on_exhausted=self._on_exhausted,
            )

        # Default: random UUIDs - use version-appropriate random generator
        return self._create_random_generator()

    def _create_random_generator(self) -> UUIDGenerator:
        """Create the appropriate random generator for the UUID version."""
        if self._uuid_version == "uuid1":
            return RandomUUID1Generator(node=self._node, clock_seq=self._clock_seq)
        if self._uuid_version == "uuid4":
            return RandomUUIDGenerator()
        if self._uuid_version == "uuid6":
            return RandomUUID6Generator(node=self._node, clock_seq=self._clock_seq)
        if self._uuid_version == "uuid7":
            return RandomUUID7Generator()
        if self._uuid_version == "uuid8":
            return RandomUUID8Generator()
        raise ValueError(f"Unknown UUID version: {self._uuid_version}")

    def _create_patched_function(self) -> Callable[..., uuid.UUID]:
        """Create the patched UUID function with ignore list and call tracking."""
        generator = self._generator
        ignore_list = self._ignore_list
        freezer = self  # Capture self for tracking
        uuid_version = self._uuid_version

        if not ignore_list:
            # Accept *args, **kwargs for compatibility with uuid1/uuid6 signatures
            def patched_uuid_func(
                *args: object,  # noqa: ARG001
                **kwargs: object,  # noqa: ARG001
            ) -> uuid.UUID:
                # skip_frames=3: _get_caller_info -> patched_uuid_func -> _proxy_uuidX -> caller
                (
                    caller_module,
                    caller_file,
                    caller_line,
                    caller_function,
                    caller_qualname,
                ) = _get_caller_info(skip_frames=3)
                result = generator()  # type: ignore[misc]
                freezer._record_call(
                    result,
                    was_mocked=True,
                    caller_module=caller_module,
                    caller_file=caller_file,
                    caller_line=caller_line,
                    caller_function=caller_function,
                    caller_qualname=caller_qualname,
                )
                return result

            return patched_uuid_func

        def patched_uuid_func_with_ignore(*args: object, **kwargs: object) -> uuid.UUID:
            # skip_frames=3: _get_caller_info -> patched_uuid_func_with_ignore -> _proxy_uuidX -> caller
            (
                caller_module,
                caller_file,
                caller_line,
                caller_function,
                caller_qualname,
            ) = _get_caller_info(skip_frames=3)

            # Walk up the call stack to check for ignored modules
            frame = inspect.currentframe()
            try:
                # Skip only this frame (patched_uuid_func_with_ignore)
                # We want to check the caller's frame and all frames above it
                if frame is not None:
                    frame = frame.f_back

                # Check if any caller should be ignored
                while frame is not None:
                    if _should_ignore_frame(frame, ignore_list):
                        result = get_original(uuid_version)(*args, **kwargs)
                        freezer._record_call(
                            result,
                            was_mocked=False,
                            caller_module=caller_module,
                            caller_file=caller_file,
                            caller_line=caller_line,
                            caller_function=caller_function,
                            caller_qualname=caller_qualname,
                        )
                        return result
                    frame = frame.f_back
            finally:
                del frame

            result = generator()  # type: ignore[misc]
            freezer._record_call(
                result,
                was_mocked=True,
                caller_module=caller_module,
                caller_file=caller_file,
                caller_line=caller_line,
                caller_function=caller_function,
                caller_qualname=caller_qualname,
            )
            return result

        return patched_uuid_func_with_ignore

    def __enter__(self) -> UUIDFreezer:
        """Start freezing the target UUID function.

        This method:
        1. Creates the UUID generator based on configuration
        2. Creates the patched UUID function with call tracking
        3. Sets the generator in the proxy's context variable

        The proxy approach means any code that captured the UUID function
        (including Pydantic default_factory) will automatically use our generator.
        """
        self._generator = self._create_generator()
        patched = self._create_patched_function()
        self._token = set_generator(patched, func_name=self._uuid_version)
        return self

    def __exit__(self, *args: object) -> None:
        """Stop freezing and restore previous uuid.uuid4() behavior.

        This method resets the context variable to its previous state,
        which may be None (no generator) or an outer context's generator.
        """
        if self._token is not None:
            reset_generator(self._token)
            self._token = None
        self._generator = None

    def __call__(
        self, func_or_class: Callable[..., object] | type
    ) -> Callable[..., object] | type:
        """Use as a decorator on functions or classes.

        When applied to a class, all test methods (methods starting with 'test')
        are wrapped to run within the frozen UUID context.
        """
        if isinstance(func_or_class, type):
            # Decorating a class - wrap all test methods
            return self._wrap_class(func_or_class)

        # Decorating a function
        @functools.wraps(func_or_class)
        def wrapper(*args: object, **kwargs: object) -> object:
            with self:
                return func_or_class(*args, **kwargs)

        return wrapper

    def _wrap_class(self, klass: type) -> type:
        """Wrap all test methods in a class with the freeze context."""
        for attr_name in dir(klass):
            if attr_name.startswith("test"):
                attr = getattr(klass, attr_name)
                if callable(attr) and not isinstance(attr, type):
                    # Create a new freezer for each method to ensure isolation
                    wrapped = self._wrap_method(attr)
                    setattr(klass, attr_name, wrapped)
        return klass

    def _wrap_method(self, method: Callable[..., object]) -> Callable[..., object]:
        """Wrap a single method with a fresh freeze context."""
        # Capture the freezer config to create fresh instances per call
        uuids = self._uuids
        uuid_version = self._uuid_version
        seed = self._seed
        on_exhausted = self._on_exhausted
        ignore_extra = self._ignore_extra
        ignore_defaults = self._ignore_defaults
        node_id = self._node_id
        node = self._node
        clock_seq = self._clock_seq

        @functools.wraps(method)
        def wrapper(*args: object, **kwargs: object) -> object:
            # Create a fresh freezer for each method call
            freezer = UUIDFreezer(
                uuids=uuids,
                uuid_version=uuid_version,
                seed=seed,
                on_exhausted=on_exhausted,
                ignore=ignore_extra if ignore_extra else None,
                ignore_defaults=ignore_defaults,
                node_id=node_id,
                node=node,
                clock_seq=clock_seq,
            )
            with freezer:
                return method(*args, **kwargs)

        return wrapper

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current generator (only available while frozen)."""
        return self._generator

    @property
    def uuid_version(self) -> str:
        """The UUID version being frozen (e.g., "uuid4", "uuid7")."""
        return self._uuid_version

    @property
    def seed(self) -> int | None:
        """The seed value used for reproducible UUID generation.

        Returns the actual integer seed being used, even when seed="node" was
        specified (in which case the seed is derived from the test's node ID).

        Returns None if:
        - Not using seeded generation (using static UUIDs or sequences)
        - A random.Random instance was passed directly (BYOP mode)
        - The freezer is not currently active
        """
        # Check if the generator has a seed property (all seeded generators do)
        if self._generator is not None and hasattr(self._generator, "seed"):
            return self._generator.seed  # type: ignore[union-attr]
        return None

    def reset(self) -> None:
        """Reset the generator and tracking data to initial state."""
        if self._generator is not None:
            self._generator.reset()
        self._reset_tracking()


# =============================================================================
# Version-specific freeze functions
# =============================================================================


# freeze_uuid4 - for uuid.uuid4()
@overload
def freeze_uuid4(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


@overload
def freeze_uuid4(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid4(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


def freeze_uuid4(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a freezer for uuid.uuid4() calls.

    This function returns a UUIDFreezer that can be used as a decorator
    or context manager to control uuid.uuid4() calls within its scope.

    Args:
        uuids: Static UUID(s) to return. Can be:
            - A single UUID string or object (always returns this UUID)
            - A sequence of UUIDs (cycles through or raises when exhausted)
        seed: Seed for reproducible UUID generation. Can be:
            - int: Create a fresh Random instance with this seed
            - random.Random: Use this Random instance directly (BYOP)
            - "node": Derive seed from pytest node ID (use with marker)
        on_exhausted: Behavior when a UUID sequence is exhausted:
            - "cycle": Loop back to the start (default)
            - "random": Fall back to random UUIDs
            - "raise": Raise UUIDsExhaustedError
        ignore: Module prefixes that should continue using real uuid4().
        ignore_defaults: Whether to include default ignore list (e.g., botocore).
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        # As a decorator with a static UUID
        @freeze_uuid4("12345678-1234-4678-8234-567812345678")
        def test_static():
            assert uuid.uuid4() == UUID("12345678-...")

        # As a decorator with a seed
        @freeze_uuid4(seed=42)
        def test_seeded():
            ...

        # As a context manager
        with freeze_uuid4("...") as freezer:
            result = uuid.uuid4()
            assert freezer.call_count == 1
    """
    return UUIDFreezer(
        uuids=uuids,
        uuid_version="uuid4",
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        ignore_defaults=ignore_defaults,
        node_id=node_id,
    )


# freeze_uuid1 - for uuid.uuid1()
@overload
def freeze_uuid1(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


@overload
def freeze_uuid1(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    node: int | None = None,
    clock_seq: int | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid1(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


def freeze_uuid1(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    node: int | None = None,
    clock_seq: int | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a freezer for uuid.uuid1() calls.

    This function returns a UUIDFreezer that can be used as a decorator
    or context manager to control uuid.uuid1() calls within its scope.

    UUID v1 is time-based with MAC address. For seeded generation, the
    time fields are generated from the random source for reproducibility.

    Args:
        uuids: Static UUID(s) to return.
        seed: Seed for reproducible UUID generation.
        node: Fixed 48-bit node (MAC address) for seeded generation.
        clock_seq: Fixed 14-bit clock sequence for seeded generation.
        on_exhausted: Behavior when a UUID sequence is exhausted.
        ignore: Module prefixes that should continue using real uuid1().
        ignore_defaults: Whether to include default ignore list.
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        @freeze_uuid1("12345678-1234-1234-8234-567812345678")
        def test_static():
            assert uuid.uuid1() == UUID("12345678-...")

        @freeze_uuid1(seed=42, node=0x123456789abc)
        def test_seeded_with_fixed_node():
            ...
    """
    return UUIDFreezer(
        uuids=uuids,
        uuid_version="uuid1",
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        ignore_defaults=ignore_defaults,
        node_id=node_id,
        node=node,
        clock_seq=clock_seq,
    )


# freeze_uuid6 - for uuid.uuid6()
@overload
def freeze_uuid6(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


@overload
def freeze_uuid6(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    node: int | None = None,
    clock_seq: int | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid6(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


def freeze_uuid6(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    node: int | None = None,
    clock_seq: int | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a freezer for uuid.uuid6() calls.

    This function returns a UUIDFreezer that can be used as a decorator
    or context manager to control uuid.uuid6() calls within its scope.

    UUID v6 is a reordered version of UUID v1 optimized for database indexing.
    Requires Python 3.14+ or the uuid6 backport package.

    Args:
        uuids: Static UUID(s) to return.
        seed: Seed for reproducible UUID generation.
        node: Fixed 48-bit node (MAC address) for seeded generation.
        clock_seq: Fixed 14-bit clock sequence for seeded generation.
        on_exhausted: Behavior when a UUID sequence is exhausted.
        ignore: Module prefixes that should continue using real uuid6().
        ignore_defaults: Whether to include default ignore list.
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        @freeze_uuid6("12345678-1234-6234-8234-567812345678")
        def test_static():
            assert uuid.uuid6() == UUID("12345678-...")

        @freeze_uuid6(seed=42)
        def test_seeded():
            ...
    """
    return UUIDFreezer(
        uuids=uuids,
        uuid_version="uuid6",
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        ignore_defaults=ignore_defaults,
        node_id=node_id,
        node=node,
        clock_seq=clock_seq,
    )


# freeze_uuid7 - for uuid.uuid7()
@overload
def freeze_uuid7(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


@overload
def freeze_uuid7(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid7(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


def freeze_uuid7(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a freezer for uuid.uuid7() calls.

    This function returns a UUIDFreezer that can be used as a decorator
    or context manager to control uuid.uuid7() calls within its scope.

    UUID v7 uses Unix timestamp (milliseconds) with random data.
    Requires Python 3.14+ or the uuid6 backport package.

    Args:
        uuids: Static UUID(s) to return.
        seed: Seed for reproducible UUID generation.
        on_exhausted: Behavior when a UUID sequence is exhausted.
        ignore: Module prefixes that should continue using real uuid7().
        ignore_defaults: Whether to include default ignore list.
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        @freeze_uuid7("01234567-89ab-7def-8123-456789abcdef")
        def test_static():
            assert uuid.uuid7() == UUID("01234567-...")

        @freeze_uuid7(seed=42)
        def test_seeded():
            ...
    """
    return UUIDFreezer(
        uuids=uuids,
        uuid_version="uuid7",
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        ignore_defaults=ignore_defaults,
        node_id=node_id,
    )


# freeze_uuid8 - for uuid.uuid8()
@overload
def freeze_uuid8(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


@overload
def freeze_uuid8(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid8(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


def freeze_uuid8(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a freezer for uuid.uuid8() calls.

    This function returns a UUIDFreezer that can be used as a decorator
    or context manager to control uuid.uuid8() calls within its scope.

    UUID v8 provides a format for experimental or vendor-specific UUIDs.
    Requires Python 3.14+ or the uuid6 backport package.

    Args:
        uuids: Static UUID(s) to return.
        seed: Seed for reproducible UUID generation.
        on_exhausted: Behavior when a UUID sequence is exhausted.
        ignore: Module prefixes that should continue using real uuid8().
        ignore_defaults: Whether to include default ignore list.
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        @freeze_uuid8("12345678-1234-8234-8234-567812345678")
        def test_static():
            assert uuid.uuid8() == UUID("12345678-...")

        @freeze_uuid8(seed=42)
        def test_seeded():
            ...
    """
    return UUIDFreezer(
        uuids=uuids,
        uuid_version="uuid8",
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        ignore_defaults=ignore_defaults,
        node_id=node_id,
    )


# =============================================================================
# Backward compatibility alias
# =============================================================================


# Convenience function for creating freezers (backward compatible alias)
@overload
def freeze_uuid(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


@overload
def freeze_uuid(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
) -> UUIDFreezer: ...


def freeze_uuid(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    ignore_defaults: bool = True,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a UUID freezer for uuid.uuid4() calls.

    .. deprecated::
        Use freeze_uuid4() instead. This function is provided for backward
        compatibility and is an alias to freeze_uuid4().

    This function returns a UUIDFreezer that can be used to control
    uuid.uuid4() calls within its scope.

    Args:
        uuids: Static UUID(s) to return. Can be:
            - A single UUID string or object (always returns this UUID)
            - A sequence of UUIDs (cycles through or raises when exhausted)
        seed: Seed for reproducible UUID generation. Can be:
            - int: Create a fresh Random instance with this seed
            - random.Random: Use this Random instance directly (BYOP)
            - "node": Derive seed from pytest node ID (use with marker)
        on_exhausted: Behavior when a UUID sequence is exhausted:
            - "cycle": Loop back to the start (default)
            - "random": Fall back to random UUIDs
            - "raise": Raise UUIDsExhaustedError
        ignore: Module prefixes that should continue using real uuid4().
        ignore_defaults: Whether to include default ignore list (e.g., botocore).
            Set to False to mock all modules including those in DEFAULT_IGNORE_PACKAGES.
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        # As a decorator with a static UUID
        @freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_static():
            assert uuid.uuid4() == UUID("12345678-...")

        # As a decorator with a sequence
        @freeze_uuid(["uuid1", "uuid2"], on_exhausted="raise")
        def test_sequence():
            ...

        # As a decorator with a seed
        @freeze_uuid(seed=42)
        def test_seeded():
            ...

        # As a context manager
        with freeze_uuid("...") as freezer:
            result = uuid.uuid4()
            freezer.reset()  # Reset to start

        # Mock everything including default-ignored packages (e.g., botocore)
        @freeze_uuid("...", ignore_defaults=False)
        def test_mock_all():
            ...
    """
    return UUIDFreezer(
        uuids=uuids,
        uuid_version="uuid4",
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        ignore_defaults=ignore_defaults,
        node_id=node_id,
    )
