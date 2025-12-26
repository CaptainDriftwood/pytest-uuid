"""Core API for pytest-uuid including the freeze_uuid decorator."""

from __future__ import annotations

import functools
import inspect
import random
import uuid
from typing import TYPE_CHECKING, Literal, overload

from pytest_uuid._tracking import (
    CallTrackingMixin,
    _find_uuid4_imports,
    _get_caller_info,
    _get_node_seed,
)
from pytest_uuid.config import get_config
from pytest_uuid.generators import (
    ExhaustionBehavior,
    RandomUUIDGenerator,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDGenerator,
    parse_uuid,
    parse_uuids,
)
from pytest_uuid.types import UUIDCall

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


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
    """Context manager and decorator for freezing uuid.uuid4() calls.

    This class provides fine-grained control over UUID generation during tests.
    It can be used as a decorator or context manager.
    """

    def __init__(
        self,
        uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
        *,
        seed: int | random.Random | Literal["node"] | None = None,
        on_exhausted: ExhaustionBehavior | str | None = None,
        ignore: Sequence[str] | None = None,
        node_id: str | None = None,
    ) -> None:
        """Initialize the UUID freezer.

        Args:
            uuids: Static UUID(s) to return. Can be a single UUID or a sequence.
            seed: Seed for reproducible UUID generation. Can be:
                - int: Create a fresh Random instance with this seed
                - random.Random: Use this Random instance directly
                - "node": Derive seed from the pytest node ID (requires node_id)
            on_exhausted: Behavior when UUID sequence is exhausted.
            ignore: Additional module prefixes to ignore (won't be patched).
            node_id: The pytest node ID (required when seed="node").
        """
        self._uuids = uuids
        self._seed = seed
        self._node_id = node_id
        self._ignore_extra = tuple(ignore) if ignore else ()

        config = get_config()
        if on_exhausted is None:
            self._on_exhausted = config.default_exhaustion_behavior
        elif isinstance(on_exhausted, str):
            self._on_exhausted = ExhaustionBehavior(on_exhausted)
        else:
            self._on_exhausted = on_exhausted

        self._ignore_list = config.get_ignore_list() + self._ignore_extra

        # These are set during __enter__
        self._generator: UUIDGenerator | None = None
        self._original_uuid4: Callable[[], uuid.UUID] | None = None
        self._patched_locations: list[tuple[object, str, object]] = []

        # Call tracking
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

    def _create_generator(self) -> UUIDGenerator:
        """Create the appropriate UUID generator based on configuration."""
        # Seeded mode takes precedence
        if self._seed is not None:
            if self._seed == "node":
                if self._node_id is None:
                    raise ValueError(
                        "seed='node' requires node_id to be provided. "
                        "Use @pytest.mark.freeze_uuid(seed='node') or pass node_id explicitly."
                    )
                actual_seed = _get_node_seed(self._node_id)
                return SeededUUIDGenerator(actual_seed)
            if isinstance(self._seed, random.Random):
                return SeededUUIDGenerator(self._seed)
            return SeededUUIDGenerator(self._seed)

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

        # Default: random UUIDs (but we still need to patch for ignore list support)
        return RandomUUIDGenerator(self._original_uuid4)

    def _create_patched_uuid4(self) -> Callable[[], uuid.UUID]:
        """Create the patched uuid4 function with ignore list and call tracking."""
        generator = self._generator
        ignore_list = self._ignore_list
        original_uuid4 = self._original_uuid4
        freezer = self  # Capture self for tracking

        if not ignore_list:

            def patched_uuid4() -> uuid.UUID:
                caller_module, caller_file = _get_caller_info(skip_frames=2)
                result = generator()  # type: ignore[misc]
                freezer._record_call(
                    result,
                    was_mocked=True,
                    caller_module=caller_module,
                    caller_file=caller_file,
                )
                return result

            return patched_uuid4

        def patched_uuid4_with_ignore() -> uuid.UUID:
            caller_module, caller_file = _get_caller_info(skip_frames=2)

            # Walk up the call stack to check for ignored modules
            frame = inspect.currentframe()
            try:
                # Skip only this frame (patched_uuid4_with_ignore)
                # We want to check the caller's frame and all frames above it
                if frame is not None:
                    frame = frame.f_back

                # Check if any caller should be ignored
                while frame is not None:
                    if _should_ignore_frame(frame, ignore_list):
                        result = original_uuid4()  # type: ignore[misc]
                        freezer._record_call(
                            result,
                            was_mocked=False,
                            caller_module=caller_module,
                            caller_file=caller_file,
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
            )
            return result

        return patched_uuid4_with_ignore

    def __enter__(self) -> UUIDFreezer:
        """Start freezing uuid.uuid4()."""
        self._original_uuid4 = uuid.uuid4
        self._generator = self._create_generator()
        patched = self._create_patched_uuid4()

        uuid4_imports = _find_uuid4_imports(self._original_uuid4)

        patches_to_apply: list[tuple[object, str, object]] = []
        patches_to_apply.append((uuid, "uuid4", self._original_uuid4))

        for module, attr_name in uuid4_imports:
            if module is not uuid:  # Skip uuid module, we already handle it
                original = getattr(module, attr_name)
                patches_to_apply.append((module, attr_name, original))

        for module, attr_name, original in patches_to_apply:
            self._patched_locations.append((module, attr_name, original))
            setattr(module, attr_name, patched)

        return self

    def __exit__(self, *args: object) -> None:
        """Stop freezing and restore original uuid.uuid4()."""
        for module, attr_name, original in self._patched_locations:
            setattr(module, attr_name, original)
        self._patched_locations.clear()
        self._generator = None
        self._original_uuid4 = None

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
        seed = self._seed
        on_exhausted = self._on_exhausted
        ignore_extra = self._ignore_extra
        node_id = self._node_id

        @functools.wraps(method)
        def wrapper(*args: object, **kwargs: object) -> object:
            # Create a fresh freezer for each method call
            freezer = UUIDFreezer(
                uuids=uuids,
                seed=seed,
                on_exhausted=on_exhausted,
                ignore=ignore_extra if ignore_extra else None,
                node_id=node_id,
            )
            with freezer:
                return method(*args, **kwargs)

        return wrapper

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current generator (only available while frozen)."""
        return self._generator

    def reset(self) -> None:
        """Reset the generator and tracking data to initial state."""
        if self._generator is not None:
            self._generator.reset()
        self._reset_tracking()


# Convenience function for creating freezers
@overload
def freeze_uuid(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID],
    *,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid(
    uuids: None = None,
    *,
    seed: int | random.Random | Literal["node"],
    ignore: Sequence[str] | None = None,
    node_id: str | None = None,
) -> UUIDFreezer: ...


@overload
def freeze_uuid(
    uuids: None = None,
    *,
    seed: None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
) -> UUIDFreezer: ...


def freeze_uuid(
    uuids: str | uuid.UUID | Sequence[str | uuid.UUID] | None = None,
    *,
    seed: int | random.Random | Literal["node"] | None = None,
    on_exhausted: ExhaustionBehavior | str | None = None,
    ignore: Sequence[str] | None = None,
    node_id: str | None = None,
) -> UUIDFreezer:
    """Create a UUID freezer for use as a decorator or context manager.

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
        node_id: The pytest node ID (required when seed="node").

    Returns:
        A UUIDFreezer that can be used as a decorator or context manager.

    Examples:
        # As a decorator with a static UUID
        @freeze_uuid("12345678-1234-5678-1234-567812345678")
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
    """
    return UUIDFreezer(
        uuids=uuids,
        seed=seed,
        on_exhausted=on_exhausted,
        ignore=ignore,
        node_id=node_id,
    )
