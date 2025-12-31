"""pytest plugin for mocking uuid.uuid4() calls."""

from __future__ import annotations

import inspect
import random
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from pytest_uuid._tracking import (
    CallTrackingMixin,
    _find_uuid4_imports,
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
from pytest_uuid.types import UUIDCall

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager


class UUIDMocker(CallTrackingMixin):
    """A class to manage mocked UUID values.

    This class provides a way to control the UUIDs returned by uuid.uuid4()
    during tests. It can return a single fixed UUID, cycle through a sequence
    of UUIDs, or generate reproducible UUIDs from a seed.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        node_id: str | None = None,
        ignore: list[str] | None = None,
    ) -> None:
        self._monkeypatch = monkeypatch
        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        # Store reference to original uuid4 to avoid recursion when patched
        self._original_uuid4 = uuid.uuid4
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

        # Ignore list handling
        config = get_config()
        self._ignore_extra = tuple(ignore) if ignore else ()
        self._ignore_list = config.get_ignore_list() + self._ignore_extra

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
                mock_uuid.set("12345678-1234-5678-1234-567812345678")
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
        # Reset ignore list to defaults
        config = get_config()
        self._ignore_list = config.get_ignore_list() + self._ignore_extra

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID.

        Returns:
            The next UUID from the generator, or a random UUID if no
            generator is configured.
        """
        caller_module, caller_file = _get_caller_info(skip_frames=2)

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
                        result = self._original_uuid4()
                        self._record_call(result, False, caller_module, caller_file)
                        return result
                    frame = frame.f_back
            finally:
                del frame

        if self._generator is not None:
            result = self._generator()
            was_mocked = True
        else:
            result = self._original_uuid4()
            was_mocked = False

        self._record_call(result, was_mocked, caller_module, caller_file)
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

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


class UUIDSpy(CallTrackingMixin):
    """A class to spy on UUID generation without mocking.

    This class wraps uuid.uuid4() to track calls while still returning
    real random UUIDs. Similar to pytest-mock's spy functionality.
    """

    def __init__(self, original_uuid4: Callable[[], uuid.UUID]) -> None:
        self._original_uuid4 = original_uuid4
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []
        self._calls: list[UUIDCall] = []

    def __call__(self) -> uuid.UUID:
        """Generate a real UUID and track it."""
        caller_module, caller_file = _get_caller_info(skip_frames=2)
        result = self._original_uuid4()
        self._record_call(
            result,
            was_mocked=False,
            caller_module=caller_module,
            caller_file=caller_file,
        )
        return result

    def reset(self) -> None:
        """Reset tracking data."""
        self._reset_tracking()


def pytest_configure(config: pytest.Config) -> None:
    """Load config from pyproject.toml and register the freeze_uuid marker."""
    from pathlib import Path

    # Set active pytest config FIRST (enables get_config() to work)
    _set_active_pytest_config(config)

    # Initialize stash with default config
    if _has_stash and _config_key is not None and hasattr(config, "stash"):
        config.stash[_config_key] = PytestUUIDConfig()

    # Load configuration from pyproject.toml (updates stash via configure())
    load_config_from_pyproject(Path(config.rootdir))  # type: ignore[unresolved-attribute]

    config.addinivalue_line(
        "markers",
        "freeze_uuid(uuids=None, *, seed=None, on_exhausted=None, ignore=None): "
        "Freeze uuid.uuid4() for this test. "
        "uuids: static UUID(s) to return. "
        "seed: int, random.Random, or 'node' for reproducible generation. "
        "on_exhausted: 'cycle', 'random', or 'raise' when sequence exhausted. "
        "ignore: module prefixes to exclude from patching.",
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
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> UUIDMocker:
    """Fixture that provides a UUIDMocker for controlling uuid.uuid4() calls.

    This fixture patches uuid.uuid4 globally AND any modules that have imported
    uuid4 directly (via `from uuid import uuid4`).

    Example:
        def test_something(mock_uuid):
            mock_uuid.set("12345678-1234-5678-1234-567812345678")
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-5678-1234-567812345678"

        def test_multiple_uuids(mock_uuid):
            mock_uuid.set(
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            )
            assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
            assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
            # Cycles back to the first UUID
            assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

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
    # Check for fixture conflict - detect if spy_uuid already patched uuid.uuid4
    if isinstance(uuid.uuid4, UUIDSpy):
        raise pytest.UsageError(
            "Cannot use both 'mock_uuid' and 'spy_uuid' fixtures in the same test. "
            "Use mock_uuid.spy() to switch to spy mode instead."
        )

    mocker = UUIDMocker(monkeypatch, node_id=request.node.nodeid)
    original_uuid4 = uuid.uuid4
    uuid4_imports = _find_uuid4_imports(original_uuid4)

    monkeypatch.setattr(uuid, "uuid4", mocker)
    for module, attr_name in uuid4_imports:
        monkeypatch.setattr(module, attr_name, mocker)

    return mocker


@pytest.fixture
def mock_uuid_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str], AbstractContextManager[UUIDMocker]]:
    """Fixture factory for mocking uuid.uuid4() in specific modules.

    Use this when you need to mock uuid.uuid4() in a specific module where
    it has been imported directly (e.g., `from uuid import uuid4`).

    Example:
        def test_with_module_mock(mock_uuid_factory):
            with mock_uuid_factory("myapp.models") as mocker:
                mocker.set("12345678-1234-5678-1234-567812345678")
                # uuid4() calls in myapp.models will return the mocked UUID
                result = create_model()  # Calls uuid4() internally
                assert result.id == "12345678-1234-5678-1234-567812345678"

    Returns:
        A context manager factory that takes a module path and yields a UUIDMocker.
    """

    @contextmanager
    def factory(module_path: str) -> Iterator[UUIDMocker]:
        mocker = UUIDMocker(monkeypatch)

        try:
            module = sys.modules[module_path]
        except KeyError:
            raise KeyError(
                f"Module '{module_path}' is not loaded. "
                f"Make sure to import the module before using mock_uuid_factory. "
                f"Example: import {module_path.split('.')[0]}"
            ) from None

        if not hasattr(module, "uuid4"):
            raise AttributeError(
                f"Module '{module_path}' does not have a 'uuid4' attribute. "
                f"This fixture only works with modules that use "
                f"'from uuid import uuid4'. "
                f"For modules using 'import uuid', use the mock_uuid fixture instead."
            )

        original = module.uuid4  # type: ignore[attr-defined]
        monkeypatch.setattr(module, "uuid4", mocker)
        try:
            yield mocker
        finally:
            monkeypatch.setattr(module, "uuid4", original)

    return factory


@pytest.fixture
def spy_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> UUIDSpy:
    """Fixture that spies on uuid.uuid4() calls without mocking.

    This fixture patches uuid.uuid4 to track all calls while still
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
    # Check for fixture conflict - detect if mock_uuid already patched uuid.uuid4
    if isinstance(uuid.uuid4, UUIDMocker):
        raise pytest.UsageError(
            "Cannot use both 'mock_uuid' and 'spy_uuid' fixtures in the same test. "
            "Use mock_uuid.spy() to switch to spy mode instead."
        )

    original_uuid4 = uuid.uuid4
    spy = UUIDSpy(original_uuid4)
    uuid4_imports = _find_uuid4_imports(original_uuid4)

    monkeypatch.setattr(uuid, "uuid4", spy)
    for module, attr_name in uuid4_imports:
        monkeypatch.setattr(module, attr_name, spy)

    return spy
