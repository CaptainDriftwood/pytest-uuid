"""pytest-uuid - A pytest plugin for mocking uuid.uuid4() calls."""

from pytest_uuid.plugin import mock_uuid, mock_uuid_factory

__version__ = "0.1.0"
__all__ = ["mock_uuid", "mock_uuid_factory"]
