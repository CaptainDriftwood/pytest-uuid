"""pytest-uuid - A pytest plugin for mocking uuid.uuid4() calls.

This plugin provides multiple ways to control UUID generation in tests:

Fixtures (recommended for most use cases):
    mock_uuid: Main fixture for controlling uuid.uuid4() calls. Use this when
        you need imperative control within a test (set UUIDs, change behavior
        mid-test, inspect calls). Automatically patches both `import uuid` and
        `from uuid import uuid4` patterns across all loaded modules.

    spy_uuid: Track uuid.uuid4() calls without mocking them. Use when you need
        to verify UUID generation happened but don't need to control the output.
        Returns real random UUIDs while recording all calls.

    mock_uuid_factory: Factory for module-specific mocking. Use when you need
        to mock uuid4 in a specific module only, not globally.

Decorator/Context Manager:
    freeze_uuid: Use as @freeze_uuid("...") decorator or with freeze_uuid("...")
        context manager. Best for declarative, self-contained test setup.
        Supports static UUIDs, sequences, and seeded generation.

Marker:
    @pytest.mark.freeze_uuid(...): Declarative marker for pytest. Supports
        seed="node" for automatic per-test reproducible UUIDs.

Architecture:
    - UUIDGenerator subclasses produce UUIDs (Static, Sequence, Seeded, Random)
    - UUIDMocker/UUIDFreezer wrap generators and handle patching
    - CallTrackingMixin provides call inspection (call_count, calls, etc.)
    - Configuration via pyproject.toml [tool.pytest_uuid] or configure()

Thread Safety:
    The mocking classes are NOT thread-safe. For multi-threaded tests, each
    thread should have its own mock setup or use appropriate synchronization.

Example:
    # Fixture approach (most common)
    def test_user_creation(mock_uuid):
        mock_uuid.set("12345678-1234-4678-8234-567812345678")
        user = create_user()
        assert user.id == "12345678-1234-4678-8234-567812345678"

    # Decorator approach
    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    def test_with_decorator():
        assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

    # Marker with node seeding (reproducible per-test)
    @pytest.mark.freeze_uuid(seed="node")
    def test_reproducible():
        result = uuid.uuid4()  # Same UUID every time this test runs
"""

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
    RandomUUID1Generator,
    RandomUUID6Generator,
    RandomUUID7Generator,
    RandomUUIDGenerator,
    SeededUUIDGenerator,
    SequenceUUIDGenerator,
    StaticUUIDGenerator,
    UUIDGenerator,
    UUIDsExhaustedError,
)
from pytest_uuid.plugin import (
    NamespaceUUIDSpy,
    UUID1Mocker,
    UUID6Mocker,
    UUID7Mocker,
    UUID8Mocker,
    UUIDMocker,
    UUIDSpy,
    mock_uuid,
    mock_uuid_factory,
    spy_uuid,
)
from pytest_uuid.types import (
    NamespaceUUIDCall,
    UUIDCall,
    UUIDMockerProtocol,
    UUIDSpyProtocol,
)

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
    "RandomUUID1Generator",
    "RandomUUID6Generator",
    "RandomUUID7Generator",
    # Enums and Exceptions
    "ExhaustionBehavior",
    "UUIDsExhaustedError",
    # Type annotations and call tracking
    "UUIDCall",
    "NamespaceUUIDCall",
    "UUIDMockerProtocol",
    "UUIDSpyProtocol",
    # Fixtures (for documentation - actual fixtures registered via plugin)
    "mock_uuid",
    "mock_uuid_factory",
    "spy_uuid",
    "UUIDMocker",
    "UUIDSpy",
    # Sub-mockers for specific UUID versions
    "UUID1Mocker",
    "UUID6Mocker",
    "UUID7Mocker",
    "UUID8Mocker",
    "NamespaceUUIDSpy",
]
