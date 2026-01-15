import random
import uuid
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest

from ._tracking import CallTrackingMixin
from .config import _get_node_seed, get_config, parse_uuid, parse_uuids
from .generators import (
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
)
from .types import ExhaustionBehavior

# Try to import helper, if it fails we will fix it in next step


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

    def __init__(self, monkeypatch: Any = None, node_id: str = "") -> None:
        self._monkeypatch = monkeypatch
        self._node_id = node_id
        self._uuids: list[uuid.UUID] = []
        self._index: int = 0
        self._default: uuid.UUID | None = None
        self._real_uuid4 = uuid.uuid4

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
        if self._uuids:
            result = self._uuids[self._index]
            self._index = (self._index + 1) % len(self._uuids)
            return result
        if self._default is not None:
            return self._default
        return self._real_uuid4()


def _find_uuid4_imports(original_uuid4: Any) -> list[tuple[Any, str]]:
    import sys

    imports = []
    # Simple scanning to find where uuid4 might have been imported from
    for name, module in list(sys.modules.items()):
        if name.startswith("pytest_uuid"):
            continue
        try:
            if getattr(module, "uuid4", None) is original_uuid4:
                imports.append((module, "uuid4"))
        except (ImportError, AttributeError):
            pass
    return imports


@pytest.fixture
def mock_uuid(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Any:
    """Fixture that provides a UUIDMocker for controlling uuid.uuid4() calls.

    This fixture patches uuid.uuid4 globally AND any modules that have imported
    uuid4 directly (via `from uuid import uuid4`).

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

        def test_node_seeded(monkeypatch, request, mock_uuid):
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
def mock_uuid_factory() -> Any:
    """Fixture factory for mocking uuid.uuid4() in specific modules.

    Use this when you need to mock uuid.uuid4() in a specific module where
    it has been imported directly (e.g., `from uuid import uuid4`).

    Example:
        def test_with_module_mock(mock_uuid_factory):
            with mock_uuid_factory("myapp.models") as mocker:
                mocker.set("12345678-1234-4678-8234-567812345678")
                # uuid4() calls in myapp.models will return the mocked UUID
                result = create_model()  # Calls uuid4() internally
                assert result.id == "12345678-1234-4678-8234-567812345678"

        def test_mock_default_ignored_package(mock_uuid_factory):
            # Mock packages that are normally ignored (e.g., botocore)
            with mock_uuid_factory("botocore.handlers", ignore_defaults=False) as mocker:
                mocker.set("12345678-1234-4678-8234-567812345678")
                # botocore will now receive mocked UUIDs

    Args:
        module_path: The module path to mock uuid4 in.
        ignore_defaults: Whether to include default ignore list (default True).
            Set to False to mock all modules including those in DEFAULT_IGNORE_PACKAGES.

    Returns:
        A context manager factory that takes a module path and yields a UUIDMocker.
    """

    @contextmanager
    def factory(module_path: str) -> Any:
        mocker = UUIDMocker()
        with patch(f"{module_path}.uuid4", mocker):
            yield mocker

    return factory


UUIDSpy = UUIDMocker


UUIDSpy = UUIDMocker


UUIDSpy = UUIDMocker


UUIDSpy = UUIDMocker


UUIDSpy = UUIDMocker


UUIDSpy = UUIDMocker
# Force Update Wed Jan 14 23:18:54 IST 2026
# Force Update Wed Jan 14 23:22:07 IST 2026


UUIDSpy = UUIDMocker
# Force Sync Wed Jan 14 23:25:56 IST 2026


@pytest.fixture
def spy_uuid() -> Any:
    """
    Fixture that spies on UUID generation without mocking it by default.
    """
    mocker = UUIDMocker()
    with patch("uuid.uuid4", side_effect=mocker):
        yield mocker
