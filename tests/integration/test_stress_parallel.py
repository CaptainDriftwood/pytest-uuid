"""Stress tests for parallel execution and fixture isolation.

These tests are designed to catch race conditions, fixture pollution,
and mock leakage when running pytest-uuid under heavy parallel load
with pytest-xdist.

CRITICAL: These tests use uuid_testpkg (an external module that imports uuid)
to test the actual scenario of mock leakage through module caching - NOT just
direct uuid.uuid4() calls.

Run locally: just test-stress
Run parallel: just test-stress-parallel 4  (or: make -j4 stress-test)
Run in CI: See .github/workflows/stress-test.yml
"""

from __future__ import annotations

import os
import uuid

import pytest

# Import the external test package that uses uuid internally
# This tests the actual mock leakage scenario through module caching
from uuid_testpkg import UUIDService, alt_generate_id, generate_id

from pytest_uuid import freeze_uuid

# --- Constants ---

# Mock UUIDs we use - unmocked tests should NEVER see these
MOCK_UUIDS = [f"{i:08x}-{i:04x}-{i:04x}-{i:04x}-{i:012x}" for i in range(1, 51)]

# Track results for isolation verification (module-level for xdist workers)
_isolation_results: dict[str, str] = {}


# --- Helper to get xdist worker ID ---


def get_worker_id() -> str:
    """Get the xdist worker ID, or 'master' if not running under xdist."""
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


# --- External module tests (the actual scenario) ---
# These test mocking uuid4 in an external module that imports uuid


@pytest.mark.parametrize("expected_uuid", MOCK_UUIDS[:15])
def test_external_module_direct_import_mocked(expected_uuid):
    """Test mocking works in external module using 'from uuid import uuid4'."""
    with freeze_uuid(expected_uuid):
        # generate_id() calls uuid4() via direct import
        result = generate_id()
        assert str(result) == expected_uuid


@pytest.mark.parametrize("expected_uuid", MOCK_UUIDS[15:30])
def test_external_module_import_uuid_mocked(expected_uuid):
    """Test mocking works in external module using 'import uuid'."""
    with freeze_uuid(expected_uuid):
        # alt_generate_id() calls uuid.uuid4() via module import
        result = alt_generate_id()
        assert str(result) == expected_uuid


@pytest.mark.parametrize("_iteration", range(20))
def test_external_module_unmocked(_iteration):
    """Test external module returns real UUIDs when not mocked."""
    result = generate_id()
    # Should be a real v4 UUID, not any of our mock UUIDs
    assert str(result) not in MOCK_UUIDS
    assert result.version == 4


# --- Interleaved mocked/unmocked (critical for detecting leakage) ---


@pytest.mark.parametrize(
    ("should_mock", "test_uuid"),
    [
        (True, "10101010-1010-4010-8010-101010101010"),
        (False, None),
        (True, "20202020-2020-4020-8020-202020202020"),
        (False, None),
        (True, "30303030-3030-4030-8030-303030303030"),
        (False, None),
        (True, "40404040-4040-4040-9040-404040404040"),
        (False, None),
        (True, "50505050-5050-4050-9050-505050505050"),
        (False, None),
    ]
    * 3,  # Repeat 3 times for more coverage
)
def test_external_module_interleaved(should_mock, test_uuid):
    """Test interleaved mocked/unmocked calls to external module.

    This is the critical test for detecting mock leakage - unmocked tests
    should NEVER see mocked values from previous tests.
    """
    if should_mock:
        with freeze_uuid(test_uuid):
            result = generate_id()
            assert str(result) == test_uuid
    else:
        result = generate_id()
        assert result.version == 4
        # CRITICAL: Should not be any mock UUID from this or other tests
        assert str(result) not in MOCK_UUIDS
        assert str(result) != "10101010-1010-4010-8010-101010101010"
        assert str(result) != "20202020-2020-4020-8020-202020202020"


# --- Service class tests (OOP pattern) ---


@pytest.mark.parametrize("expected_uuid", MOCK_UUIDS[:10])
def test_service_class_mocked(expected_uuid):
    """Test mocking works with service class methods."""
    service = UUIDService(prefix="test")
    with freeze_uuid(expected_uuid):
        result = service.create_id()
        assert str(result) == expected_uuid


@pytest.mark.parametrize("_iteration", range(10))
def test_service_class_unmocked(_iteration):
    """Test service class returns real UUIDs when not mocked."""
    service = UUIDService(prefix="test")
    result = service.create_id()
    assert str(result) not in MOCK_UUIDS
    assert result.version == 4


# --- Fixture-based tests ---


@pytest.mark.parametrize("expected_uuid", MOCK_UUIDS[:15])
def test_fixture_with_external_module(mock_uuid, expected_uuid):
    """Test mock_uuid fixture works with external module."""
    mock_uuid.uuid4.set(expected_uuid)
    result = generate_id()
    assert str(result) == expected_uuid


# --- Nested context tests ---


@pytest.mark.parametrize(
    ("outer_uuid", "inner_uuid"),
    [
        (
            "aaaa0000-0000-4000-8000-000000000000",
            "bbbb0000-0000-4000-8000-000000000000",
        ),
        (
            "aaaa1111-1111-4111-8111-111111111111",
            "bbbb1111-1111-4111-8111-111111111111",
        ),
        (
            "aaaa2222-2222-4222-8222-222222222222",
            "bbbb2222-2222-4222-8222-222222222222",
        ),
    ],
)
def test_nested_contexts_external_module(outer_uuid, inner_uuid):
    """Test nested contexts work correctly with external module."""
    with freeze_uuid(outer_uuid):
        assert str(generate_id()) == outer_uuid
        with freeze_uuid(inner_uuid):
            assert str(generate_id()) == inner_uuid
        # Back to outer
        assert str(generate_id()) == outer_uuid


# --- Seeded tests with external module ---


@pytest.mark.parametrize("seed", [42, 123, 456, 789, 1000])
def test_seeded_external_module(seed):
    """Test seeded UUIDs work with external module."""
    with freeze_uuid(seed=seed):
        result1 = generate_id()
        result2 = generate_id()
        # Each call should produce different UUIDs
        assert result1 != result2
        # Both should be valid v4 UUIDs
        assert result1.version == 4
        assert result2.version == 4


# --- Rapid generation tests ---


@pytest.mark.parametrize("_batch", range(5))
def test_rapid_external_module_unmocked(_batch):
    """Test rapid UUID generation via external module without mocking."""
    results = [generate_id() for _ in range(50)]
    # All should be unique
    assert len({str(r) for r in results}) == 50
    # All should be v4
    assert all(r.version == 4 for r in results)
    # None should be our mock UUIDs
    assert all(str(r) not in MOCK_UUIDS for r in results)


@pytest.mark.parametrize("batch_num", range(5))
def test_rapid_external_module_mocked(batch_num):
    """Test rapid mocked generation via external module."""
    test_uuid = (
        f"{batch_num:08x}-{batch_num:04x}-{batch_num:04x}-{batch_num:04x}-"
        f"{batch_num:012x}"
    )
    with freeze_uuid(test_uuid):
        results = [generate_id() for _ in range(50)]
        # All should be the same mocked UUID
        assert all(str(r) == test_uuid for r in results)


# --- Worker isolation tests ---


def test_worker_isolation_mocked_01():
    """Mocked test 1 - stores result for verification."""
    worker = get_worker_id()
    with freeze_uuid("a0a0a0a0-1111-4111-8111-111111111111"):
        result = generate_id()
        _isolation_results[f"{worker}_mocked_01"] = str(result)
        assert str(result) == "a0a0a0a0-1111-4111-8111-111111111111"


def test_worker_isolation_unmocked_01():
    """Unmocked test 1 - should NEVER see mocked values."""
    worker = get_worker_id()
    result = generate_id()
    _isolation_results[f"{worker}_unmocked_01"] = str(result)
    # Must be real UUID
    assert result.version == 4
    assert str(result) != "a0a0a0a0-1111-4111-8111-111111111111"
    assert str(result) not in MOCK_UUIDS


def test_worker_isolation_mocked_02():
    """Mocked test 2 - stores result for verification."""
    worker = get_worker_id()
    with freeze_uuid("b0b0b0b0-2222-4222-8222-222222222222"):
        result = generate_id()
        _isolation_results[f"{worker}_mocked_02"] = str(result)
        assert str(result) == "b0b0b0b0-2222-4222-8222-222222222222"


def test_worker_isolation_unmocked_02():
    """Unmocked test 2 - should NEVER see mocked values."""
    worker = get_worker_id()
    result = generate_id()
    _isolation_results[f"{worker}_unmocked_02"] = str(result)
    # Must be real UUID
    assert result.version == 4
    assert str(result) != "b0b0b0b0-2222-4222-8222-222222222222"
    assert str(result) not in MOCK_UUIDS


# --- Decorator tests with external module ---


@freeze_uuid("deadbeef-dead-4eef-aead-beefdeadbeef")
def test_decorator_external_module():
    """Test @freeze_uuid decorator works with external module."""
    result = generate_id()
    assert str(result) == "deadbeef-dead-4eef-aead-beefdeadbeef"


# --- Marker tests ---


@pytest.mark.freeze_uuid("ffffffff-ffff-4fff-afff-ffffffffffff")
def test_marker_external_module():
    """Test @pytest.mark.freeze_uuid works with external module."""
    result = generate_id()
    assert str(result) == "ffffffff-ffff-4fff-afff-ffffffffffff"


# --- Clean state verification tests ---
# These run without any mocking and MUST get real UUIDs


def test_verify_clean_state_external_01():
    """Verify no mock pollution in external module - test 1."""
    result = generate_id()
    assert result.version == 4
    assert str(result) not in MOCK_UUIDS


def test_verify_clean_state_external_02():
    """Verify no mock pollution in external module - test 2."""
    result = alt_generate_id()
    assert result.version == 4
    assert str(result) not in MOCK_UUIDS


def test_verify_clean_state_external_03():
    """Verify no mock pollution in service class - test 3."""
    service = UUIDService()
    result = service.create_id()
    assert result.version == 4
    assert str(result) not in MOCK_UUIDS


# --- Direct uuid.uuid4() tests (baseline) ---
# Keep a few direct tests to verify basic functionality


@pytest.mark.parametrize("expected_uuid", MOCK_UUIDS[:5])
def test_direct_uuid4_mocked(expected_uuid):
    """Baseline: direct uuid.uuid4() mocking."""
    with freeze_uuid(expected_uuid):
        result = uuid.uuid4()
        assert str(result) == expected_uuid


@pytest.mark.parametrize("_iteration", range(5))
def test_direct_uuid4_unmocked(_iteration):
    """Baseline: direct uuid.uuid4() unmocked."""
    result = uuid.uuid4()
    assert result.version == 4
    assert str(result) not in MOCK_UUIDS
