"""pytest plugin for mocking uuid.uuid4() calls."""

from __future__ import annotations

import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


class UUIDMocker:
    """A class to manage mocked UUID values.

    This class provides a way to control the UUIDs returned by uuid.uuid4()
    during tests. It can return a single fixed UUID or cycle through a
    sequence of UUIDs.
    """

    def __init__(self) -> None:
        self._uuids: list[uuid.UUID] = []
        self._index: int = 0
        self._default: uuid.UUID | None = None
        # Store reference to original uuid4 to avoid recursion when patched
        self._original_uuid4 = uuid.uuid4

    def set(self, *uuids: str | uuid.UUID) -> None:
        """Set the UUID(s) to return.

        Args:
            *uuids: One or more UUIDs (as strings or UUID objects) to return.
                   If multiple UUIDs are provided, they will be returned in
                   sequence, cycling back to the beginning when exhausted.
        """
        self._uuids = [uuid.UUID(u) if isinstance(u, str) else u for u in uuids]
        self._index = 0

    def set_default(self, default_uuid: str | uuid.UUID) -> None:
        """Set a default UUID to return when no specific UUIDs are set.

        Args:
            default_uuid: The UUID to use as default.
        """
        self._default = (
            uuid.UUID(default_uuid) if isinstance(default_uuid, str) else default_uuid
        )

    def reset(self) -> None:
        """Reset the mocker to its initial state."""
        self._uuids = []
        self._index = 0
        self._default = None

    def __call__(self) -> uuid.UUID:
        """Return the next mocked UUID.

        Returns:
            The next UUID in the sequence, or the default UUID if set,
            or a new random UUID if neither is configured.
        """
        if self._uuids:
            result = self._uuids[self._index]
            self._index = (self._index + 1) % len(self._uuids)
            return result
        if self._default is not None:
            return self._default
        return self._original_uuid4()


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


@pytest.fixture
def mock_uuid(monkeypatch: pytest.MonkeyPatch) -> Iterator[UUIDMocker]:
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

    Yields:
        UUIDMocker: An object to control the mocked UUIDs.
    """
    mocker = UUIDMocker()
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
        mocker = UUIDMocker()
        module = sys.modules[module_path]
        original = module.uuid4  # type: ignore[attr-defined]
        monkeypatch.setattr(module, "uuid4", mocker)
        try:
            yield mocker
        finally:
            monkeypatch.setattr(module, "uuid4", original)

    return factory
