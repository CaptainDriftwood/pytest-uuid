"""Tests for pytest-uuid fixtures (mock_uuid, spy_uuid, mock_uuid_factory).

This file consolidates tests for all fixture functionality:
- mock_uuid: Basic operations, enhanced features, call tracking
- spy_uuid: Spy-only mode
- mock_uuid_factory: Module-specific mocking
- UUIDCall dataclass
"""

from __future__ import annotations

import random
import uuid
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from pytest_uuid.generators import ExhaustionBehavior, UUIDsExhaustedError
from pytest_uuid.types import UUIDCall

# --- mock_uuid basic operations ---


def test_mock_uuid_set_single_uuid(mock_uuid):
    """Test setting a single UUID."""
    expected = "12345678-1234-4678-8234-567812345678"
    mock_uuid.uuid4.set(expected)

    result = uuid.uuid4()

    assert str(result) == expected


def test_mock_uuid_works_with_direct_import(mock_uuid):
    """Test that mock works with 'from uuid import uuid4' pattern."""
    expected = "12345678-1234-4678-8234-567812345678"
    mock_uuid.uuid4.set(expected)

    # Use the directly imported uuid4 function
    result = uuid4()

    assert str(result) == expected


def test_mock_uuid_set_single_uuid_as_object(mock_uuid):
    """Test setting a UUID using a UUID object."""
    expected = uuid.UUID("12345678-1234-4678-8234-567812345678")
    mock_uuid.uuid4.set(expected)

    result = uuid.uuid4()

    assert result == expected


def test_mock_uuid_set_default(mock_uuid):
    """Test setting a default UUID."""
    default = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    mock_uuid.uuid4.set_default(default)

    # All calls return the default
    assert str(uuid.uuid4()) == default
    assert str(uuid.uuid4()) == default
    assert str(uuid.uuid4()) == default


def test_mock_uuid_set_overrides_default(mock_uuid):
    """Test that set() overrides the default."""
    default = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    specific = "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"

    mock_uuid.uuid4.set_default(default)
    mock_uuid.uuid4.set(specific)

    assert str(uuid.uuid4()) == specific


def test_mock_uuid_reset_clears_everything(mock_uuid):
    """Test that reset() clears all configuration."""
    mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
    mock_uuid.uuid4.set_default("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")

    mock_uuid.uuid4.reset()

    # Should return a real random UUID now
    result = uuid.uuid4()
    assert result != uuid.UUID("12345678-1234-4678-8234-567812345678")
    assert result != uuid.UUID("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")


def test_mock_uuid_no_mock_returns_random(mock_uuid):  # noqa: ARG001
    """Test that without configuration, random UUIDs are returned."""
    result1 = uuid.uuid4()
    result2 = uuid.uuid4()

    # Should be valid UUIDs but different from each other
    assert isinstance(result1, uuid.UUID)
    assert isinstance(result2, uuid.UUID)
    assert result1 != result2


# --- mock_uuid enhanced features ---


def test_mock_uuid_set_seed_integer(mock_uuid):
    """Test set_seed with integer seed."""
    mock_uuid.uuid4.set_seed(42)
    first = uuid.uuid4()

    mock_uuid.uuid4.set_seed(42)
    second = uuid.uuid4()

    assert first == second


def test_mock_uuid_set_seed_random_instance(mock_uuid):
    """Test set_seed with Random instance."""
    rng = random.Random(42)
    mock_uuid.uuid4.set_seed(rng)

    result = uuid.uuid4()
    assert isinstance(result, uuid.UUID)
    assert result.version == 4


def test_mock_uuid_set_seed_from_node(mock_uuid):
    """Test set_seed_from_node uses test node ID."""
    mock_uuid.uuid4.set_seed_from_node()
    first = uuid.uuid4()

    mock_uuid.uuid4.set_seed_from_node()
    second = uuid.uuid4()

    # Same test, same node ID, same seed
    assert first == second


def test_mock_uuid_seed_property_with_integer(mock_uuid):
    """Test that seed property returns the integer seed."""
    mock_uuid.uuid4.set_seed(42)
    assert mock_uuid.uuid4.seed == 42


def test_mock_uuid_seed_property_with_random_instance(mock_uuid):
    """Test that seed property returns None when using Random instance."""
    rng = random.Random(42)
    mock_uuid.uuid4.set_seed(rng)
    assert mock_uuid.uuid4.seed is None


def test_mock_uuid_seed_property_from_node(mock_uuid):
    """Test that seed property returns computed seed from node ID."""
    mock_uuid.uuid4.set_seed_from_node()
    # Should return an integer derived from the node ID
    assert mock_uuid.uuid4.seed is not None
    assert isinstance(mock_uuid.uuid4.seed, int)


def test_mock_uuid_seed_property_with_static_uuid(mock_uuid):
    """Test that seed property returns None when using static UUIDs."""
    mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
    assert mock_uuid.uuid4.seed is None


def test_mock_uuid_seed_property_no_generator(mock_uuid):
    """Test that seed property returns None when no generator is set."""
    assert mock_uuid.uuid4.seed is None


@pytest.mark.parametrize(
    "behavior_input",
    [
        "raise",
        ExhaustionBehavior.RAISE,
    ],
)
def test_mock_uuid_set_exhaustion_behavior(mock_uuid, behavior_input):
    """Test setting exhaustion behavior with string or enum."""
    mock_uuid.uuid4.set_exhaustion_behavior(behavior_input)
    mock_uuid.uuid4.set("11111111-1111-4111-8111-111111111111")

    uuid.uuid4()

    with pytest.raises(UUIDsExhaustedError):
        uuid.uuid4()


def test_mock_uuid_generator_property(mock_uuid):
    """Test the generator property."""
    assert mock_uuid.uuid4.generator is None

    mock_uuid.uuid4.set_seed(42)
    assert mock_uuid.uuid4.generator is not None

    mock_uuid.uuid4.reset()
    assert mock_uuid.uuid4.generator is None


# --- mock_uuid_factory ---


def test_mock_uuid_factory_creates_scoped_mocker(mock_uuid_factory):
    """Test that the factory creates a scoped mocker via proxy."""
    expected = "12345678-1234-4678-8234-567812345678"

    # With proxy approach, module_path is optional (for backward compat)
    with mock_uuid_factory() as mocker:
        mocker.uuid4.set(expected)
        result = uuid.uuid4()

    assert str(result) == expected


def test_mock_uuid_factory_returns_mocker_with_all_methods(mock_uuid_factory):
    """Test that the factory returns a fully functional mocker."""
    with mock_uuid_factory() as mocker:
        # Test set
        mocker.uuid4.set("11111111-1111-4111-8111-111111111111")
        assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

        # Test reset
        mocker.reset()

        # Test set_default
        mocker.uuid4.set_default("22222222-2222-4222-8222-222222222222")
        assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"


def test_mock_uuid_factory_accepts_module_path_for_backward_compat(mock_uuid_factory):
    """Test that factory accepts module_path for backward compatibility."""
    expected = "12345678-1234-4678-8234-567812345678"

    # module_path is accepted but no longer used for validation
    with mock_uuid_factory("uuid") as mocker:
        mocker.uuid4.set(expected)
        result = uuid.uuid4()

    assert str(result) == expected


# --- Plugin integration ---


def test_mock_uuid_fixture_is_available(mock_uuid):
    """Test that the mock_uuid fixture is automatically available."""
    assert mock_uuid is not None


def test_mock_uuid_factory_fixture_is_available(mock_uuid_factory):
    """Test that the mock_uuid_factory fixture is automatically available."""
    assert mock_uuid_factory is not None
    assert callable(mock_uuid_factory)


def test_mock_uuid_factory_ignore_defaults_true_by_default(mock_uuid_factory):
    """Test that ignore_defaults=True is the default behavior."""
    with mock_uuid_factory() as mocker:
        # Access uuid4 to initialize the sub-mocker
        # Default behavior: botocore should be in the ignore list
        assert "botocore" in mocker.uuid4._ignore_list


def test_mock_uuid_factory_ignore_defaults_false(mock_uuid_factory):
    """Test that ignore_defaults=False excludes default packages from ignore list."""
    with mock_uuid_factory(ignore_defaults=False) as mocker:
        # Access uuid4 to initialize the sub-mocker
        # With ignore_defaults=False, botocore should NOT be in the ignore list
        assert "botocore" not in mocker.uuid4._ignore_list


# --- Edge cases ---


def test_mock_uuid_empty_set_call(mock_uuid):
    """Test calling set() with no arguments."""
    mock_uuid.uuid4.set()  # Should not raise
    # Should return random UUIDs since no UUIDs were set
    result = uuid.uuid4()
    assert isinstance(result, uuid.UUID)


def test_mock_uuid_invalid_uuid_string_raises(mock_uuid):
    """Test that invalid UUID strings raise an error."""
    with pytest.raises(ValueError):
        mock_uuid.uuid4.set("not-a-valid-uuid")


def test_mock_uuid_set_can_be_called_multiple_times(mock_uuid):
    """Test that calling set() multiple times replaces previous values."""
    mock_uuid.uuid4.set("11111111-1111-4111-8111-111111111111")
    assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

    mock_uuid.uuid4.set("22222222-2222-4222-8222-222222222222")
    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"


# --- mock_uuid call tracking integration ---


def test_mock_uuid_tracking_with_mocked_uuids(mock_uuid):
    """Test that tracking works correctly with mocked UUIDs."""
    mock_uuid.uuid4.set(
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    )

    result1 = uuid.uuid4()
    result2 = uuid.uuid4()

    assert mock_uuid.uuid4.call_count == 2
    assert mock_uuid.uuid4.generated_uuids == [result1, result2]
    assert mock_uuid.uuid4.last_uuid == result2
    assert mock_uuid.uuid4.mocked_count == 2
    assert all(c.was_mocked for c in mock_uuid.uuid4.calls)


def test_mock_uuid_tracking_with_real_uuids(mock_uuid):
    """Test that tracking works in spy mode (real UUIDs but tracked)."""
    # Enable spy mode explicitly - this registers the uuid4 mocker
    mock_uuid.uuid4.spy()
    result = uuid.uuid4()

    assert mock_uuid.uuid4.call_count == 1
    assert mock_uuid.uuid4.last_uuid == result
    assert mock_uuid.uuid4.real_count == 1


# --- spy_uuid fixture ---


def test_spy_uuid_returns_real_uuids(spy_uuid):  # noqa: ARG001
    """Test that spy returns real random UUIDs."""
    result1 = uuid.uuid4()
    result2 = uuid.uuid4()

    # Real UUIDs should be different
    assert result1 != result2
    assert result1.version == 4
    assert result2.version == 4


def test_spy_uuid_integrates_call_tracking(spy_uuid):
    """Test that spy_uuid properly integrates CallTrackingMixin."""
    result1 = uuid.uuid4()
    result2 = uuid.uuid4()

    assert spy_uuid.call_count == 2
    assert spy_uuid.generated_uuids == [result1, result2]
    assert spy_uuid.last_uuid == result2
    # All spy calls should be marked as not mocked
    assert all(not c.was_mocked for c in spy_uuid.calls)


# --- mock_uuid spy mode ---


def test_mock_uuid_spy_method_returns_real_uuids(mock_uuid):
    """Test that spy mode returns real UUIDs."""
    mock_uuid.uuid4.spy()

    result1 = uuid.uuid4()
    result2 = uuid.uuid4()

    assert result1 != result2
    assert result1.version == 4


def test_mock_uuid_spy_mode_still_tracks(mock_uuid):
    """Test that spy mode still tracks calls."""
    mock_uuid.uuid4.spy()

    result = uuid.uuid4()

    assert mock_uuid.uuid4.call_count == 1
    assert mock_uuid.uuid4.last_uuid == result


def test_mock_uuid_spy_after_set(mock_uuid):
    """Test switching to spy mode after setting UUIDs."""
    mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
    uuid.uuid4()  # Returns mocked

    mock_uuid.uuid4.spy()
    result = uuid.uuid4()  # Returns real

    # Real UUID should be different from the mocked one
    assert result != uuid.UUID("12345678-1234-4678-8234-567812345678")
    assert mock_uuid.uuid4.call_count == 2


def test_mock_uuid_spy_mode_tracks_all_calls(mock_uuid):
    """Test that spy mode tracks all calls including before spy()."""
    mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
    uuid.uuid4()  # Mocked call

    mock_uuid.uuid4.spy()
    uuid.uuid4()  # Real call

    # Both calls should be tracked
    assert mock_uuid.uuid4.call_count == 2
    assert len(mock_uuid.uuid4.generated_uuids) == 2


# --- UUIDCall tracking integration ---


def test_uuid_call_captures_caller_info(spy_uuid):
    """Test that calls capture caller module and file via _get_caller_info."""
    uuid.uuid4()

    calls = spy_uuid.calls
    assert len(calls) == 1

    call = calls[0]
    # Should capture this test module
    assert call.caller_module is not None
    assert "test_fixtures" in call.caller_module
    assert call.caller_file is not None
    assert call.caller_file.endswith(".py")


def test_uuid_call_mocked_vs_real_separation(mock_uuid):
    """Test separation of mocked and real (spy mode) calls."""
    mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
    mocked_result = uuid.uuid4()  # Mocked

    mock_uuid.uuid4.spy()
    real_result = uuid.uuid4()  # Real

    # Check mocked_calls
    mocked = mock_uuid.uuid4.mocked_calls
    assert len(mocked) == 1
    assert mocked[0].uuid == mocked_result
    assert mocked[0].was_mocked is True

    # Check real_calls
    real = mock_uuid.uuid4.real_calls
    assert len(real) == 1
    assert real[0].uuid == real_result
    assert real[0].was_mocked is False


# --- UUIDCall dataclass ---


def test_uuid_call_is_frozen():
    """Test that UUIDCall is immutable."""
    call = UUIDCall(
        uuid=uuid.UUID("12345678-1234-4678-8234-567812345678"),
        was_mocked=True,
        caller_module="test_module",
        caller_file="/path/to/test.py",
    )

    # Attempting to modify should raise FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        call.was_mocked = False


def test_uuid_call_fields():
    """Test UUIDCall field values."""
    test_uuid = uuid.UUID("12345678-1234-4678-8234-567812345678")
    call = UUIDCall(
        uuid=test_uuid,
        was_mocked=True,
        caller_module="myapp.models",
        caller_file="/app/models.py",
    )

    assert call.uuid == test_uuid
    assert call.was_mocked is True
    assert call.caller_module == "myapp.models"
    assert call.caller_file == "/app/models.py"


def test_uuid_call_optional_fields():
    """Test UUIDCall with optional fields as None."""
    test_uuid = uuid.UUID("12345678-1234-4678-8234-567812345678")
    call = UUIDCall(
        uuid=test_uuid,
        was_mocked=False,
    )

    assert call.uuid == test_uuid
    assert call.was_mocked is False
    assert call.caller_module is None
    assert call.caller_file is None


# --- Fixture conflict detection (requires pytester) ---


def test_spy_uuid_then_mock_uuid_uuid4_conflict_raises_error(pytester):
    """Test that accessing mock_uuid.uuid4 when spy_uuid is active raises UsageError."""
    pytester.makepyfile(
        test_conflict="""
        import uuid

        def test_spy_active_then_mock_uuid4_access(spy_uuid, mock_uuid):
            # spy_uuid activates and starts tracking
            uuid.uuid4()  # This activates spy_uuid

            # Now accessing mock_uuid.uuid4 should raise UsageError
            # because spy_uuid (UUIDSpy) is already on the generator stack
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*UsageError*Cannot use both*mock_uuid*spy_uuid*"])


def test_mock_uuid_uuid4_then_spy_uuid_conflict_raises_error(pytester):
    """Test that spy_uuid raises UsageError when mock_uuid.uuid4 is active."""
    pytester.makepyfile(
        test_conflict="""
        import uuid

        def test_mock_active_then_spy_request(mock_uuid, spy_uuid):
            # First activate mock_uuid.uuid4
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            uuid.uuid4()  # Use the mock

            # Now spy_uuid should conflict because UUID4Mocker is active
            # The spy_uuid fixture will error when it tries to activate
            _ = spy_uuid.call_count
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*UsageError*Cannot use both*mock_uuid*spy_uuid*"])
