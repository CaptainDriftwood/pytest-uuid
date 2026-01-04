"""Integration tests for test isolation and scoping.

These tests verify that pytest-uuid correctly isolates state between tests
and supports various scoping patterns (test, class, module, session).
"""

from __future__ import annotations

# --- Test isolation ---


def test_fixture_isolation_between_tests(pytester):
    """Test that mock_uuid fixture is isolated between tests."""
    pytester.makepyfile(
        test_isolation="""
        import uuid

        def test_first(mock_uuid):
            mock_uuid.set("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
            assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

        def test_second(mock_uuid):
            # Should NOT be affected by first test
            # Without setting anything, we get random UUIDs
            result = uuid.uuid4()
            assert str(result) != "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
            assert isinstance(result, uuid.UUID)
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_marker_isolation_between_tests(pytester):
    """Test that marker freezing is isolated between tests."""
    pytester.makepyfile(
        test_marker_isolation="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
        def test_with_marker():
            assert str(uuid.uuid4()) == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"

        def test_after_marker(mock_uuid):
            # Should have clean state - not affected by previous marker
            result = uuid.uuid4()
            assert str(result) != "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_decorator_isolation_between_tests(pytester):
    """Test that @freeze_uuid decorator is isolated between tests."""
    pytester.makepyfile(
        test_decorator_isolation="""
        import uuid
        from pytest_uuid import freeze_uuid

        @freeze_uuid("cccccccc-cccc-4ccc-accc-cccccccccccc")
        def test_with_decorator():
            assert str(uuid.uuid4()) == "cccccccc-cccc-4ccc-accc-cccccccccccc"

        def test_after_decorator():
            # Should have clean state
            result = uuid.uuid4()
            assert str(result) != "cccccccc-cccc-4ccc-accc-cccccccccccc"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


# --- Scoped mocking ---


def test_module_level_pytestmark(pytester):
    """Test module-level pytestmark applies to all tests in module."""
    pytester.makepyfile(
        test_module_mark="""
        import uuid
        import pytest

        pytestmark = pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")

        def test_one():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

        def test_two():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

        class TestNested:
            def test_three(self):
                assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=3)


def test_module_level_pytestmark_with_seed(pytester):
    """Test module-level pytestmark with seeded UUIDs."""
    pytester.makepyfile(
        test_module_seed="""
        import uuid
        import pytest

        pytestmark = pytest.mark.freeze_uuid(seed=42)

        def test_seeded_one():
            result = uuid.uuid4()
            assert result.version == 4

        def test_seeded_two():
            result = uuid.uuid4()
            assert result.version == 4
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_class_decorator_freeze_uuid(pytester):
    """Test @freeze_uuid decorator on a test class."""
    pytester.makepyfile(
        test_class_decorator="""
        import uuid
        from pytest_uuid import freeze_uuid

        @freeze_uuid("12345678-1234-4678-8234-567812345678")
        class TestWithDecorator:
            def test_one(self):
                assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

            def test_two(self):
                assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

            def helper_method(self):
                # Non-test methods are NOT wrapped
                return uuid.uuid4()
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_class_decorator_with_seed(pytester):
    """Test @freeze_uuid(seed=...) decorator on a test class."""
    pytester.makepyfile(
        test_class_seeded="""
        import uuid
        from pytest_uuid import freeze_uuid

        @freeze_uuid(seed=42)
        class TestSeededClass:
            def test_one(self):
                result = uuid.uuid4()
                assert result.version == 4

            def test_two(self):
                # Each method gets fresh seeded generator
                result = uuid.uuid4()
                assert result.version == 4
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_class_decorator_method_isolation(pytester):
    """Test that each method in decorated class gets fresh context."""
    pytester.makepyfile(
        test_class_isolation="""
        import uuid
        from pytest_uuid import freeze_uuid

        @freeze_uuid([
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ])
        class TestMethodIsolation:
            def test_one(self):
                # First method starts at beginning of sequence
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
                assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"

            def test_two(self):
                # Second method ALSO starts at beginning (fresh context)
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
                assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_session_scoped_fixture(pytester):
    """Test session-scoped autouse fixture freezes across files."""
    pytester.makeconftest(
        """
        import pytest
        from pytest_uuid import freeze_uuid

        @pytest.fixture(scope="session", autouse=True)
        def freeze_all_uuids():
            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                yield
        """
    )

    pytester.makepyfile(
        test_file_a="""
        import uuid

        def test_in_file_a():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
        """
    )

    pytester.makepyfile(
        test_file_b="""
        import uuid

        def test_in_file_b():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_session_scoped_seeded_fixture(pytester):
    """Test session-scoped seeded fixture maintains sequence across tests."""
    pytester.makeconftest(
        """
        import pytest
        from pytest_uuid import freeze_uuid

        @pytest.fixture(scope="session", autouse=True)
        def freeze_seeded():
            with freeze_uuid(seed=42):
                yield
        """
    )

    pytester.makepyfile(
        test_session_seed="""
        import uuid

        def test_session_scope_produces_different_uuids():
            # Session scope means sequence continues across calls
            # Each call should produce a different UUID
            uuid1 = uuid.uuid4()
            uuid2 = uuid.uuid4()
            uuid3 = uuid.uuid4()

            # All should be different (sequence advances)
            assert uuid1 != uuid2
            assert uuid2 != uuid3
            assert uuid1 != uuid3

            # All should be valid v4 UUIDs
            assert uuid1.version == 4
            assert uuid2.version == 4
            assert uuid3.version == 4
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_module_scoped_fixture(pytester):
    """Test module-scoped fixture resets between modules."""
    pytester.makeconftest(
        """
        import pytest
        from pytest_uuid import freeze_uuid

        @pytest.fixture(scope="module", autouse=True)
        def freeze_per_module():
            with freeze_uuid(seed=42):
                yield
        """
    )

    # This test verifies that module-scoped fixtures reset between modules
    # by checking that the first UUID from seed=42 is deterministic
    pytester.makepyfile(
        test_mod_a="""
        import uuid

        # Expected first UUID from seed=42
        EXPECTED_FIRST = "bdd640fb-0667-4ad1-9c80-317fa3b1799d"

        def test_first_uuid_is_deterministic():
            result = uuid.uuid4()
            assert str(result) == EXPECTED_FIRST

        def test_second_uuid_is_different():
            # Within same module, sequence continues
            result = uuid.uuid4()
            assert str(result) != EXPECTED_FIRST
        """
    )

    pytester.makepyfile(
        test_mod_b="""
        import uuid

        # Same expected first UUID - new module resets the fixture
        EXPECTED_FIRST = "bdd640fb-0667-4ad1-9c80-317fa3b1799d"

        def test_module_reset_gives_same_first_uuid():
            # New module = fresh fixture = sequence restarts
            result = uuid.uuid4()
            assert str(result) == EXPECTED_FIRST
        """
    )

    # Disable pytest-randomly for this test since it relies on test order
    # within each module (but not across modules)
    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=3)


# --- Mock leakage through module caching ---


def test_mock_does_not_leak_via_module_cache_direct_import(pytester):
    """Test that mocked uuid4 in external module doesn't leak between tests.

    This tests the edge case where:
    1. An external module uses `from uuid import uuid4` (direct import)
    2. Test 1 uses freeze_uuid - the module should be patched
    3. Test 2 has NO mocking - the module should get REAL UUIDs
    4. Test 3 uses freeze_uuid with different UUID - module gets new mock
    5. Test 4 has NO mocking - module should get REAL UUIDs again

    If cleanup fails, Test 2 or Test 4 would see stale mocked values.
    """
    # Create an external package that uses direct import
    pytester.makepyfile(
        uuid_service="""
from uuid import uuid4

def generate_id():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_mock_leakage="""
import uuid
import pytest
from pytest_uuid import freeze_uuid
import uuid_service

results = {}

@freeze_uuid("11111111-1111-4111-8111-111111111111")
def test_01_with_mocking():
    result = uuid_service.generate_id()
    results["test_01"] = str(result)
    assert str(result) == "11111111-1111-4111-8111-111111111111"

def test_02_without_mocking():
    result = uuid_service.generate_id()
    results["test_02"] = str(result)
    # Should NOT be the mocked value from test_01
    assert str(result) != "11111111-1111-4111-8111-111111111111"
    assert result.version == 4

@freeze_uuid("22222222-2222-4222-8222-222222222222")
def test_03_with_different_mock():
    result = uuid_service.generate_id()
    results["test_03"] = str(result)
    assert str(result) == "22222222-2222-4222-8222-222222222222"

def test_04_without_mocking_again():
    result = uuid_service.generate_id()
    results["test_04"] = str(result)
    assert str(result) != "11111111-1111-4111-8111-111111111111"
    assert str(result) != "22222222-2222-4222-8222-222222222222"
    assert result.version == 4

def test_05_verify_all_results():
    assert results["test_01"] == "11111111-1111-4111-8111-111111111111"
    assert results["test_02"] != "11111111-1111-4111-8111-111111111111"
    assert results["test_03"] == "22222222-2222-4222-8222-222222222222"
    assert results["test_04"] != "11111111-1111-4111-8111-111111111111"
    assert results["test_04"] != "22222222-2222-4222-8222-222222222222"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=5)


def test_mock_does_not_leak_via_module_cache_import_uuid(pytester):
    """Test mock cleanup works with 'import uuid' pattern."""
    pytester.makepyfile(
        import_uuid_service="""
import uuid

def generate():
    return uuid.uuid4()
"""
    )

    pytester.makepyfile(
        test_import_pattern_leakage="""
import pytest
from pytest_uuid import freeze_uuid
import import_uuid_service

results = {}

@freeze_uuid("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
def test_01_mocked():
    result = import_uuid_service.generate()
    results["test_01"] = str(result)
    assert str(result) == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"

def test_02_not_mocked():
    result = import_uuid_service.generate()
    results["test_02"] = str(result)
    assert str(result) != "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
    assert result.version == 4

def test_03_verify():
    assert results["test_01"] == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
    assert results["test_02"] != "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=3)


def test_first_test_unmocked_then_mocked_then_unmocked(pytester):
    """Test: first test unmocked, second mocked, third unmocked.

    This tests that a module imported and used without mocking
    can be properly mocked in a subsequent test, then properly
    restored for a following unmocked test.
    """
    pytester.makepyfile(
        first_unmocked_service="""
from uuid import uuid4

def get_uuid():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_first_unmocked="""
import pytest
from pytest_uuid import freeze_uuid
import first_unmocked_service

results = {}

def test_01_no_mocking():
    result = first_unmocked_service.get_uuid()
    results["test_01"] = str(result)
    assert result.version == 4

@freeze_uuid("34343434-3434-4434-8434-343434343434")
def test_02_with_mocking():
    result = first_unmocked_service.get_uuid()
    results["test_02"] = str(result)
    assert str(result) == "34343434-3434-4434-8434-343434343434"

def test_03_no_mocking_again():
    result = first_unmocked_service.get_uuid()
    results["test_03"] = str(result)
    assert str(result) != "34343434-3434-4434-8434-343434343434"
    assert result.version == 4

def test_04_verify():
    assert results["test_01"] != "34343434-3434-4434-8434-343434343434"
    assert results["test_02"] == "34343434-3434-4434-8434-343434343434"
    assert results["test_03"] != "34343434-3434-4434-8434-343434343434"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=4)


def test_alternating_mocked_unmocked_many_times(pytester):
    """Test many alternations between mocked and unmocked tests."""
    pytester.makepyfile(
        alternating_service="""
from uuid import uuid4

def gen():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_alternating="""
import pytest
from pytest_uuid import freeze_uuid
import alternating_service

results = []

@freeze_uuid("11111111-1111-4111-8111-111111111111")
def test_01_mocked():
    result = alternating_service.gen()
    results.append(("test_01", str(result), True))
    assert str(result) == "11111111-1111-4111-8111-111111111111"

def test_02_unmocked():
    result = alternating_service.gen()
    results.append(("test_02", str(result), False))
    assert str(result) != "11111111-1111-4111-8111-111111111111"

@freeze_uuid("22222222-2222-4222-8222-222222222222")
def test_03_mocked():
    result = alternating_service.gen()
    results.append(("test_03", str(result), True))
    assert str(result) == "22222222-2222-4222-8222-222222222222"

def test_04_unmocked():
    result = alternating_service.gen()
    results.append(("test_04", str(result), False))
    assert str(result) != "22222222-2222-4222-8222-222222222222"

@freeze_uuid("33333333-3333-4333-8333-333333333333")
def test_05_mocked():
    result = alternating_service.gen()
    results.append(("test_05", str(result), True))
    assert str(result) == "33333333-3333-4333-8333-333333333333"

def test_06_unmocked():
    result = alternating_service.gen()
    results.append(("test_06", str(result), False))
    assert str(result) != "33333333-3333-4333-8333-333333333333"

@freeze_uuid("44444444-4444-4444-9444-444444444444")
def test_07_mocked():
    result = alternating_service.gen()
    results.append(("test_07", str(result), True))
    assert str(result) == "44444444-4444-4444-9444-444444444444"

def test_08_unmocked():
    result = alternating_service.gen()
    results.append(("test_08", str(result), False))
    assert str(result) != "44444444-4444-4444-9444-444444444444"

def test_09_final_verify():
    mocked_uuids = [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
        "44444444-4444-4444-9444-444444444444",
    ]
    for name, uuid_str, was_mocked in results:
        if was_mocked:
            assert uuid_str in mocked_uuids, f"{name} should have a mocked UUID"
        else:
            assert uuid_str not in mocked_uuids, f"{name} leaked mock: {uuid_str}"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=9)


def test_mock_cleanup_with_nested_package(pytester):
    """Test mock cleanup works with nested package structures."""
    pytester.mkpydir("external_pkg")
    pytester.makepyfile(
        **{
            "external_pkg/utils/__init__": "",
            "external_pkg/utils/ids": """
from uuid import uuid4

def create_unique_id():
    return uuid4()
""",
        }
    )

    pytester.makepyfile(
        test_nested_pkg_leakage="""
import pytest
from pytest_uuid import freeze_uuid
from external_pkg.utils import ids

results = {}

@freeze_uuid("12121212-1212-4212-8212-121212121212")
def test_01_mocked():
    result = ids.create_unique_id()
    results["test_01"] = str(result)
    assert str(result) == "12121212-1212-4212-8212-121212121212"

def test_02_not_mocked():
    result = ids.create_unique_id()
    results["test_02"] = str(result)
    assert str(result) != "12121212-1212-4212-8212-121212121212"
    assert result.version == 4

def test_03_verify():
    assert results["test_01"] == "12121212-1212-4212-8212-121212121212"
    assert results["test_02"] != "12121212-1212-4212-8212-121212121212"
"""
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=3)
