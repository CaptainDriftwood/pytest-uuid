import uuid
from typing import Any
from unittest.mock import patch

import pytest


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
        self._real_uuid4 = uuid.uuid4

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
        return self._real_uuid4()


@pytest.fixture
def mock_uuid() -> Any:
    """Fixture that provides a UUIDMocker for controlling uuid.uuid4() calls.

    This fixture patches uuid.uuid4 globally, allowing you to control what
    UUIDs are returned during your tests.

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
    with patch("uuid.uuid4", mocker):
        yield mocker


@pytest.fixture
def mock_uuid_factory() -> Any:
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
    from contextlib import contextmanager

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
