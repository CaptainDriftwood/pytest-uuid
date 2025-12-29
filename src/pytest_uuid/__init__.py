"""pytest-uuid - A pytest plugin for mocking uuid.uuid4() calls."""

from importlib.metadata import PackageNotFoundError, version

from pytest_uuid.api import UUIDFreezer, freeze_uuid
from pytest_uuid.config import (
    configure,
    get_config,
    load_config_from_pyproject,
    reset_config,
)
from pytest_uuid.generators import (
    ExhaustionBehavior,
    RandomUUIDGenerator,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDGenerator,
    UUIDsExhaustedError,
)
from pytest_uuid.plugin import (
    UUIDMocker,
    UUIDSpy,
    mock_uuid,
    mock_uuid_factory,
    spy_uuid,
)
from pytest_uuid.types import UUIDMockerProtocol, UUIDSpyProtocol

try:
    __version__ = version("pytest-uuid")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"
__all__ = [
    # Main API
    "freeze_uuid",
    "UUIDFreezer",
    # Configuration
    "configure",
    "get_config",
    "reset_config",
    "load_config_from_pyproject",
    # Generators
    "UUIDGenerator",
    "StaticUUIDGenerator",
    "SequenceUUIDGenerator",
    "SeededUUIDGenerator",
    "RandomUUIDGenerator",
    # Enums and Exceptions
    "ExhaustionBehavior",
    "UUIDsExhaustedError",
    # Type annotations
    "UUIDMockerProtocol",
    "UUIDSpyProtocol",
    # Fixtures (for documentation - actual fixtures registered via plugin)
    "mock_uuid",
    "mock_uuid_factory",
    "spy_uuid",
    "UUIDMocker",
    "UUIDSpy",
]
