"""Integration tests for test isolation and scoping.

These tests verify that pytest-uuid correctly isolates state between tests
and supports various scoping patterns (test, class, module, session).
"""

from __future__ import annotations


class TestTestIsolation:
    """Tests for test isolation - ensuring tests don't affect each other."""

    def test_fixture_isolation_between_tests(self, pytester):
        """Test that mock_uuid fixture is isolated between tests."""
        pytester.makepyfile(
            test_isolation="""
            import uuid

            def test_first(mock_uuid):
                mock_uuid.set("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
                assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

            def test_second(mock_uuid):
                # Should NOT be affected by first test
                # Without setting anything, we get random UUIDs
                result = uuid.uuid4()
                assert str(result) != "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                assert isinstance(result, uuid.UUID)
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_marker_isolation_between_tests(self, pytester):
        """Test that marker freezing is isolated between tests."""
        pytester.makepyfile(
            test_marker_isolation="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
            def test_with_marker():
                assert str(uuid.uuid4()) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

            def test_after_marker(mock_uuid):
                # Should have clean state - not affected by previous marker
                result = uuid.uuid4()
                assert str(result) != "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_decorator_isolation_between_tests(self, pytester):
        """Test that @freeze_uuid decorator is isolated between tests."""
        pytester.makepyfile(
            test_decorator_isolation="""
            import uuid
            from pytest_uuid import freeze_uuid

            @freeze_uuid("cccccccc-cccc-cccc-cccc-cccccccccccc")
            def test_with_decorator():
                assert str(uuid.uuid4()) == "cccccccc-cccc-cccc-cccc-cccccccccccc"

            def test_after_decorator():
                # Should have clean state
                result = uuid.uuid4()
                assert str(result) != "cccccccc-cccc-cccc-cccc-cccccccccccc"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)


class TestScopedMocking:
    """Tests for module-level, class-level, and session-level mocking."""

    def test_module_level_pytestmark(self, pytester):
        """Test module-level pytestmark applies to all tests in module."""
        pytester.makepyfile(
            test_module_mark="""
            import uuid
            import pytest

            pytestmark = pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")

            def test_one():
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

            def test_two():
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

            class TestNested:
                def test_three(self):
                    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)

    def test_module_level_pytestmark_with_seed(self, pytester):
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

    def test_class_decorator_freeze_uuid(self, pytester):
        """Test @freeze_uuid decorator on a test class."""
        pytester.makepyfile(
            test_class_decorator="""
            import uuid
            from pytest_uuid import freeze_uuid

            @freeze_uuid("12345678-1234-5678-1234-567812345678")
            class TestWithDecorator:
                def test_one(self):
                    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

                def test_two(self):
                    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

                def helper_method(self):
                    # Non-test methods are NOT wrapped
                    return uuid.uuid4()
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_class_decorator_with_seed(self, pytester):
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

    def test_class_decorator_method_isolation(self, pytester):
        """Test that each method in decorated class gets fresh context."""
        pytester.makepyfile(
            test_class_isolation="""
            import uuid
            from pytest_uuid import freeze_uuid

            @freeze_uuid([
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ])
            class TestMethodIsolation:
                def test_one(self):
                    # First method starts at beginning of sequence
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
                    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

                def test_two(self):
                    # Second method ALSO starts at beginning (fresh context)
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
                    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_session_scoped_fixture(self, pytester):
        """Test session-scoped autouse fixture freezes across files."""
        pytester.makeconftest(
            """
            import pytest
            from pytest_uuid import freeze_uuid

            @pytest.fixture(scope="session", autouse=True)
            def freeze_all_uuids():
                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    yield
            """
        )

        pytester.makepyfile(
            test_file_a="""
            import uuid

            def test_in_file_a():
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
            """
        )

        pytester.makepyfile(
            test_file_b="""
            import uuid

            def test_in_file_b():
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_session_scoped_seeded_fixture(self, pytester):
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

    def test_module_scoped_fixture(self, pytester):
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
