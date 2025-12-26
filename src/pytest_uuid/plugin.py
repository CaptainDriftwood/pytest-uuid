"""pytest plugin for mocking uuid.uuid4() calls."""

from __future__ import annotations

import hashlib
import random
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

from pytest_uuid.api import UUIDFreezer
from pytest_uuid.config import get_config, load_config_from_pyproject
from pytest_uuid.generators import (
    ExhaustionBehavior,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDGenerator,
    parse_uuid,
    parse_uuids,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _get_node_seed(node_id: str) -> int:
    """Generate a deterministic seed from a test node ID."""
    return int(hashlib.md5(node_id.encode()).hexdigest()[:8], 16)  # noqa: S324


class UUIDMocker:
    """A class to manage mocked UUID values.

    This class provides a way to control the UUIDs returned by uuid.uuid4()
    during tests. It can return a single fixed UUID, cycle through a sequence
    of UUIDs, or generate reproducible UUIDs from a seed.
    """

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        node_id: str | None = None,
    ) -> None:
        self._monkeypatch = monkeypatch
        self._node_id = node_id
        self._generator: UUIDGenerator | None = None
        self._on_exhausted: ExhaustionBehavior = (
            get_config().default_exhaustion_behavior
        )
        # Store reference to original uuid4 to avoid recursion when patched
        self._original_uuid4 = uuid.uuid4
        # Tracking for inspection helpers
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []

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

        # Update existing sequence generator if present
        if isinstance(self._generator, SequenceUUIDGenerator):
            self._generator._on_exhausted = self._on_exhausted

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._generator = None
        self._call_count = 0
        self._generated_uuids.clear()

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID.

        Returns:
            The next UUID from the generator, or a random UUID if no
            generator is configured.
        """
        if self._generator is not None:
            result = self._generator()
        else:
            result = self._original_uuid4()
        self._call_count += 1
        self._generated_uuids.append(result)
        return result

    @property
    def generator(self) -> UUIDGenerator | None:
        """Get the current UUID generator."""
        return self._generator

    @property
    def call_count(self) -> int:
        """Get the number of times uuid4 was called."""
        return self._call_count

    @property
    def generated_uuids(self) -> list[uuid.UUID]:
        """Get a list of all UUIDs that have been generated.

        Returns a copy to prevent external modification.
        """
        return list(self._generated_uuids)

    @property
    def last_uuid(self) -> uuid.UUID | None:
        """Get the most recently generated UUID, or None if none generated."""
        return self._generated_uuids[-1] if self._generated_uuids else None

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


class UUIDSpy:
    """A class to spy on UUID generation without mocking.

    This class wraps uuid.uuid4() to track calls while still returning
    real random UUIDs. Similar to pytest-mock's spy functionality.
    """

    def __init__(self, original_uuid4: Callable[[], uuid.UUID]) -> None:
        self._original_uuid4 = original_uuid4
        self._call_count: int = 0
        self._generated_uuids: list[uuid.UUID] = []

    def __call__(self) -> uuid.UUID:
        """Generate a real UUID and track it."""
        result = self._original_uuid4()
        self._call_count += 1
        self._generated_uuids.append(result)
        return result

    @property
    def call_count(self) -> int:
        """Get the number of times uuid4 was called."""
        return self._call_count

    @property
    def generated_uuids(self) -> list[uuid.UUID]:
        """Get a list of all UUIDs that have been generated.

        Returns a copy to prevent external modification.
        """
        return list(self._generated_uuids)

    @property
    def last_uuid(self) -> uuid.UUID | None:
        """Get the most recently generated UUID, or None if none generated."""
        return self._generated_uuids[-1] if self._generated_uuids else None

    def reset(self) -> None:
        """Reset tracking data."""
        self._call_count = 0
        self._generated_uuids.clear()


def _find_uuid4_imports(original_uuid4: object) -> list[tuple[object, str]]:
    """Find all modules that have imported uuid4 directly.

    Returns a list of (module, attribute_name) tuples for modules that have
    the original uuid4 function as an attribute.
    """
    imports = []
    for module in sys.modules.values():
        if module is None:
            continue
        try:
            for attr_name in dir(module):
                if attr_name == "uuid4":
                    attr = getattr(module, attr_name, None)
                    if attr is original_uuid4:
                        imports.append((module, attr_name))
        except Exception:  # noqa: BLE001
            # Some modules may raise errors when accessing attributes
            continue
    return imports


def pytest_configure(config: pytest.Config) -> None:
    """Load config from pyproject.toml and register the freeze_uuid marker."""
    from pathlib import Path

    # Load config from pyproject.toml if present
    load_config_from_pyproject(Path(config.rootdir))

    # Register the freeze_uuid marker
    config.addinivalue_line(
        "markers",
        "freeze_uuid(uuids=None, *, seed=None, on_exhausted=None, ignore=None): "
        "Freeze uuid.uuid4() for this test. "
        "uuids: static UUID(s) to return. "
        "seed: int, random.Random, or 'node' for reproducible generation. "
        "on_exhausted: 'cycle', 'random', or 'raise' when sequence exhausted. "
        "ignore: module prefixes to exclude from patching.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Handle freeze_uuid markers on tests."""
    marker = item.get_closest_marker("freeze_uuid")
    if marker is None:
        return

    # Extract marker arguments
    args = marker.args
    kwargs = dict(marker.kwargs)

    # Handle positional argument (uuids)
    uuids = args[0] if args else kwargs.pop("uuids", None)

    # Handle node-seeded mode
    seed = kwargs.get("seed")
    if seed == "node":
        kwargs["node_id"] = item.nodeid

    # Create and enter the freezer
    freezer = UUIDFreezer(uuids=uuids, **kwargs)
    freezer.__enter__()

    # Store the freezer for cleanup
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
) -> Iterator[UUIDMocker]:
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

    Yields:
        UUIDMocker: An object to control the mocked UUIDs.
    """
    mocker = UUIDMocker(monkeypatch, node_id=request.node.nodeid)
    original_uuid4 = uuid.uuid4

    # Find all modules that have imported uuid4 directly
    uuid4_imports = _find_uuid4_imports(original_uuid4)

    # Patch uuid.uuid4 in the uuid module
    monkeypatch.setattr(uuid, "uuid4", mocker)

    # Patch uuid4 in all modules that imported it directly
    for module, attr_name in uuid4_imports:
        monkeypatch.setattr(module, attr_name, mocker)

    yield mocker


@pytest.fixture
def uuid_freezer(
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> Iterator[UUIDMocker]:
    """Alternative fixture name following the freezegun naming pattern.

    This is an alias for mock_uuid. Use whichever name you prefer.

    Yields:
        UUIDMocker: An object to control the mocked UUIDs.
    """
    mocker = UUIDMocker(monkeypatch, node_id=request.node.nodeid)
    original_uuid4 = uuid.uuid4

    # Find all modules that have imported uuid4 directly
    uuid4_imports = _find_uuid4_imports(original_uuid4)

    # Patch uuid.uuid4 in the uuid module
    monkeypatch.setattr(uuid, "uuid4", mocker)

    # Patch uuid4 in all modules that imported it directly
    for module, attr_name in uuid4_imports:
        monkeypatch.setattr(module, attr_name, mocker)

    yield mocker


@pytest.fixture
def mock_uuid_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str], Iterator[UUIDMocker]]:
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
        module = sys.modules[module_path]
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
) -> Iterator[UUIDSpy]:
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

    Yields:
        UUIDSpy: An object to inspect uuid4 calls.
    """
    original_uuid4 = uuid.uuid4
    spy = UUIDSpy(original_uuid4)

    # Find all modules that have imported uuid4 directly
    uuid4_imports = _find_uuid4_imports(original_uuid4)

    # Patch uuid.uuid4 in the uuid module
    monkeypatch.setattr(uuid, "uuid4", spy)

    # Patch uuid4 in all modules that imported it directly
    for module, attr_name in uuid4_imports:
        monkeypatch.setattr(module, attr_name, spy)

    yield spy
