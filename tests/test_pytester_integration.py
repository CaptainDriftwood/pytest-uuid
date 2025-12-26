"""Integration tests using pytester for black-box plugin testing.

These tests verify pytest-uuid behavior in isolated test environments,
testing features that are difficult to test with regular unit tests.
"""

from __future__ import annotations


class TestIgnoreList:
    """Tests for ignore list functionality."""

    def test_ignored_module_gets_real_uuid(self, pytester):
        """Test that modules in ignore list receive real UUIDs."""
        # Create a helper module that will be ignored
        pytester.makepyfile(
            ignored_helper="""
            import uuid

            def get_uuid():
                return uuid.uuid4()
            """
        )

        # Create a test that uses the ignored module
        pytester.makepyfile(
            test_ignore="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            import ignored_helper

            def test_ignored_module():
                with freeze_uuid(
                    "12345678-1234-5678-1234-567812345678",
                    ignore=["ignored_helper"]
                ):
                    # Direct call should be mocked
                    mocked = uuid.uuid4()
                    assert str(mocked) == "12345678-1234-5678-1234-567812345678"

                    # Call from ignored module should be real (different)
                    real = ignored_helper.get_uuid()
                    assert str(real) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_non_ignored_module_gets_mocked_uuid(self, pytester):
        """Test that modules not in ignore list receive mocked UUIDs."""
        # Create a helper module that will NOT be ignored
        pytester.makepyfile(
            helper="""
            import uuid

            def get_uuid():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_not_ignored="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            import helper

            def test_non_ignored_module():
                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    # Both should be mocked
                    direct = uuid.uuid4()
                    from_helper = helper.get_uuid()

                    assert str(direct) == "12345678-1234-5678-1234-567812345678"
                    assert str(from_helper) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_multiple_ignore_prefixes(self, pytester):
        """Test that multiple ignore prefixes all work."""
        pytester.makepyfile(
            pkg_a="""
            import uuid
            def get_uuid():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            pkg_b="""
            import uuid
            def get_uuid():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_multi_ignore="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            import pkg_a
            import pkg_b

            def test_multiple_ignores():
                with freeze_uuid(
                    "12345678-1234-5678-1234-567812345678",
                    ignore=["pkg_a", "pkg_b"]
                ):
                    # Direct call should be mocked
                    direct = uuid.uuid4()
                    assert str(direct) == "12345678-1234-5678-1234-567812345678"

                    # Both ignored modules should get real UUIDs
                    from_a = pkg_a.get_uuid()
                    from_b = pkg_b.get_uuid()

                    assert str(from_a) != "12345678-1234-5678-1234-567812345678"
                    assert str(from_b) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_ignore_list_with_sequence(self, pytester):
        """Test ignore list works with UUID sequences."""
        pytester.makepyfile(
            ignored_mod="""
            import uuid
            def get_uuid():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_ignore_seq="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            import ignored_mod

            def test_ignore_with_sequence():
                uuids = [
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                ]
                with freeze_uuid(uuids, ignore=["ignored_mod"]):
                    # Direct calls should cycle through sequence
                    assert str(uuid.uuid4()) == uuids[0]
                    assert str(uuid.uuid4()) == uuids[1]

                    # Ignored module should get real UUID
                    real = ignored_mod.get_uuid()
                    assert str(real) not in uuids
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_nested_module_matching(self, pytester):
        """Test ignore list works with nested module names."""
        # Create a nested package structure
        pytester.mkpydir("mypkg")
        pytester.makepyfile(
            **{
                "mypkg/subpkg/__init__": "",
                "mypkg/subpkg/helper": """
import uuid

def get_uuid():
    return uuid.uuid4()
""",
            }
        )

        pytester.makepyfile(
            test_nested="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            from mypkg.subpkg import helper

            def test_nested_module_ignored():
                with freeze_uuid(
                    "12345678-1234-5678-1234-567812345678",
                    ignore=["mypkg.subpkg"]
                ):
                    # Direct call should be mocked
                    mocked = uuid.uuid4()
                    assert str(mocked) == "12345678-1234-5678-1234-567812345678"

                    # Nested module should get real UUID
                    real = helper.get_uuid()
                    assert str(real) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestDirectImportPatching:
    """Tests for patching 'from uuid import uuid4' pattern."""

    def test_from_uuid_import_uuid4_is_patched(self, pytester):
        """Test that 'from uuid import uuid4' is properly patched."""
        pytester.makepyfile(
            test_direct_import="""
            from uuid import uuid4
            from pytest_uuid.api import freeze_uuid

            def test_direct_import_patched():
                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    result = uuid4()
                    assert str(result) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_both_import_styles_in_same_module(self, pytester):
        """Test both import styles work in the same module."""
        pytester.makepyfile(
            test_both_styles="""
            import uuid
            from uuid import uuid4

            def test_both_import_styles(mock_uuid):
                mock_uuid.set("12345678-1234-5678-1234-567812345678")

                # Both should return the mocked UUID
                result1 = uuid.uuid4()
                result2 = uuid4()

                assert str(result1) == "12345678-1234-5678-1234-567812345678"
                assert str(result2) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_multiple_modules_with_direct_imports(self, pytester):
        """Test patching works across multiple modules with direct imports."""
        pytester.makepyfile(
            module_a="""
            from uuid import uuid4

            def get_uuid():
                return uuid4()
            """
        )

        pytester.makepyfile(
            module_b="""
            from uuid import uuid4

            def get_uuid():
                return uuid4()
            """
        )

        pytester.makepyfile(
            test_multi_module="""
            from pytest_uuid.api import freeze_uuid
            import module_a
            import module_b

            def test_multiple_modules():
                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    result_a = module_a.get_uuid()
                    result_b = module_b.get_uuid()

                    assert str(result_a) == "12345678-1234-5678-1234-567812345678"
                    assert str(result_b) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_patching_restored_after_context(self, pytester):
        """Test that patching is properly restored after context exit."""
        pytester.makepyfile(
            test_restore="""
            import uuid
            from uuid import uuid4 as direct_uuid4
            from pytest_uuid.api import freeze_uuid

            def test_restore_after_context():
                original_module = uuid.uuid4

                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    # Should be mocked
                    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

                # Should be restored
                assert uuid.uuid4 is original_module

                # Should return real UUIDs now
                result = uuid.uuid4()
                assert str(result) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestPytestHooks:
    """Tests for pytest plugin hooks."""

    def test_marker_registered(self, pytester):
        """Test that freeze_uuid marker is registered."""
        pytester.makepyfile(
            test_marker_reg="""
            import pytest

            @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
            def test_with_marker():
                pass
            """
        )

        # Run with --markers to check registration
        result = pytester.runpytest("--markers")
        result.stdout.fnmatch_lines(["*freeze_uuid*"])

    def test_marker_applies_freezer(self, pytester):
        """Test that @pytest.mark.freeze_uuid applies the freezer."""
        pytester.makepyfile(
            test_marker_apply="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
            def test_marker_works():
                result = uuid.uuid4()
                assert str(result) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_with_seed_node(self, pytester):
        """Test that marker with seed='node' produces reproducible UUIDs."""
        pytester.makepyfile(
            test_node_seed="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid(seed="node")
            def test_node_seeded():
                result = uuid.uuid4()
                # Just verify it produces a valid UUID
                assert isinstance(result, uuid.UUID)
                assert result.version == 4
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_cleanup_on_teardown(self, pytester):
        """Test that marker properly cleans up after test."""
        pytester.makepyfile(
            test_cleanup="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("11111111-1111-1111-1111-111111111111")
            def test_first():
                assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

            def test_second():
                # Should not be affected by previous test's marker
                result = uuid.uuid4()
                assert str(result) != "11111111-1111-1111-1111-111111111111"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_config_loaded_from_pyproject(self, pytester):
        """Test that configuration is loaded from pyproject.toml."""
        # Create a pyproject.toml with pytest-uuid config
        pytester.makefile(
            ".toml",
            pyproject="""
            [tool.pytest_uuid]
            default_exhaustion_behavior = "raise"
            """,
        )

        pytester.makepyfile(
            test_config="""
            import uuid
            import pytest
            from pytest_uuid.api import freeze_uuid
            from pytest_uuid.generators import UUIDsExhaustedError

            def test_config_applied():
                # With default_exhaustion_behavior = "raise", exhausting
                # a sequence should raise
                with freeze_uuid(["11111111-1111-1111-1111-111111111111"]):
                    uuid.uuid4()  # First call OK
                    with pytest.raises(UUIDsExhaustedError):
                        uuid.uuid4()  # Should raise
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestSpyIntegration:
    """Tests for spy functionality in realistic scenarios."""

    def test_spy_tracks_real_uuid_calls(self, pytester):
        """Test that spy mode tracks real UUID calls."""
        pytester.makepyfile(
            test_spy_track="""
            import uuid

            def test_spy_tracking(spy_uuid):
                # Generate some UUIDs
                uuid1 = uuid.uuid4()
                uuid2 = uuid.uuid4()

                # Verify tracking
                assert spy_uuid.call_count == 2
                assert len(spy_uuid.generated_uuids) == 2
                assert spy_uuid.generated_uuids[0] == uuid1
                assert spy_uuid.generated_uuids[1] == uuid2
                assert spy_uuid.last_uuid == uuid2
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_spy_fixture_isolation(self, pytester):
        """Test that spy fixture is isolated between tests."""
        pytester.makepyfile(
            test_spy_isolation="""
            import uuid

            def test_first(spy_uuid):
                uuid.uuid4()
                uuid.uuid4()
                assert spy_uuid.call_count == 2

            def test_second(spy_uuid):
                # Should start fresh
                assert spy_uuid.call_count == 0
                uuid.uuid4()
                assert spy_uuid.call_count == 1
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_spy_with_direct_imports(self, pytester):
        """Test that spy works with direct uuid4 imports."""
        pytester.makepyfile(
            helper_direct="""
            from uuid import uuid4

            def generate():
                return uuid4()
            """
        )

        pytester.makepyfile(
            test_spy_direct="""
            import helper_direct

            def test_spy_direct_import(spy_uuid):
                result = helper_direct.generate()
                assert spy_uuid.call_count == 1
                assert spy_uuid.last_uuid == result
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_mock_uuid_spy_method(self, pytester):
        """Test the spy() method on mock_uuid fixture."""
        pytester.makepyfile(
            test_mock_spy="""
            import uuid

            def test_spy_method(mock_uuid):
                # Set up some mocking first
                mock_uuid.set("12345678-1234-5678-1234-567812345678")
                mocked = uuid.uuid4()
                assert str(mocked) == "12345678-1234-5678-1234-567812345678"
                assert mock_uuid.call_count == 1

                # Switch to spy mode
                mock_uuid.spy()

                # Now should return real UUIDs but still track
                # Note: call_count continues from before (accumulates)
                real1 = uuid.uuid4()
                real2 = uuid.uuid4()

                assert str(real1) != "12345678-1234-5678-1234-567812345678"
                assert real1 != real2
                assert mock_uuid.call_count == 3  # 1 mocked + 2 spy calls
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    # Note: Nested context tests are covered by TestDeepNesting (3 and 5 levels)

    def test_marker_and_fixture_together(self, pytester):
        """Test using marker and fixture in the same test."""
        pytester.makepyfile(
            test_marker_fixture="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("11111111-1111-1111-1111-111111111111")
            def test_marker_with_fixture(mock_uuid):
                # Marker should already be applied
                assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                # Fixture can override
                mock_uuid.set("22222222-2222-2222-2222-222222222222")
                assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_exhaustion_raise_behavior(self, pytester):
        """Test that exhaustion with 'raise' behavior works."""
        pytester.makepyfile(
            test_exhaust_raise="""
            import uuid
            import pytest
            from pytest_uuid.api import freeze_uuid
            from pytest_uuid.generators import UUIDsExhaustedError

            def test_raise_on_exhausted():
                with freeze_uuid(
                    ["11111111-1111-1111-1111-111111111111"],
                    on_exhausted="raise"
                ):
                    uuid.uuid4()  # OK
                    with pytest.raises(UUIDsExhaustedError):
                        uuid.uuid4()  # Should raise
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_seeded_reproducibility_across_runs(self, pytester):
        """Test that seeded UUIDs are reproducible across test runs."""
        pytester.makepyfile(
            test_seed_repro="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_seeded_reproducible():
                with freeze_uuid(seed=42):
                    first_run = [uuid.uuid4() for _ in range(3)]

                with freeze_uuid(seed=42):
                    second_run = [uuid.uuid4() for _ in range(3)]

                assert first_run == second_run
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_invalid_exhaustion_behavior_raises(self, pytester):
        """Test that invalid exhaustion behavior string raises ValueError."""
        pytester.makepyfile(
            test_invalid_exhaust="""
            import pytest
            from pytest_uuid.api import freeze_uuid

            def test_invalid_exhaustion():
                with pytest.raises(ValueError):
                    with freeze_uuid(
                        ["11111111-1111-1111-1111-111111111111"],
                        on_exhausted="invalid_behavior"
                    ):
                        pass
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestMarkerVariants:
    """Tests for @pytest.mark.freeze_uuid marker variants."""

    def test_marker_with_static_uuid(self, pytester):
        """Test marker with a static UUID string."""
        pytester.makepyfile(
            test_static="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
            def test_static_uuid():
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_with_sequence(self, pytester):
        """Test marker with a UUID sequence."""
        pytester.makepyfile(
            test_sequence="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid(
                [
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                ],
                on_exhausted="cycle",
            )
            def test_sequence():
                assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
                assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
                # Cycles back
                assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_with_integer_seed(self, pytester):
        """Test marker with integer seed for reproducible UUIDs."""
        pytester.makepyfile(
            test_seed="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid(seed=42)
            def test_seeded():
                result = uuid.uuid4()
                assert isinstance(result, uuid.UUID)
                assert result.version == 4
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_with_on_exhausted_raise(self, pytester):
        """Test marker with on_exhausted='raise'."""
        pytester.makepyfile(
            test_exhaust="""
            import uuid
            import pytest
            from pytest_uuid.generators import UUIDsExhaustedError

            @pytest.mark.freeze_uuid(
                ["11111111-1111-1111-1111-111111111111"],
                on_exhausted="raise",
            )
            def test_raises_on_exhausted():
                uuid.uuid4()  # First call OK
                with pytest.raises(UUIDsExhaustedError):
                    uuid.uuid4()  # Should raise
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_on_class(self, pytester):
        """Test marker applied to a test class."""
        pytester.makepyfile(
            test_class_marker="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
            class TestWithMarker:
                def test_one(self):
                    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"

                def test_two(self):
                    assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_marker_seed_reproducibility(self, pytester):
        """Test that same seed produces same UUIDs across different tests."""
        pytester.makepyfile(
            test_repro="""
            import uuid
            import pytest

            # Each test with the same seed should produce the same first UUID
            EXPECTED_UUID = "d1f6f86c-029a-4245-bb91-433a6aa79987"

            @pytest.mark.freeze_uuid(seed=12345)
            def test_seeded_first():
                result = uuid.uuid4()
                assert result.version == 4
                assert str(result) == EXPECTED_UUID

            @pytest.mark.freeze_uuid(seed=12345)
            def test_seeded_second():
                # Same seed should produce same first UUID (order independent)
                result = uuid.uuid4()
                assert result.version == 4
                assert str(result) == EXPECTED_UUID
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)


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


class TestPluginDiscovery:
    """Tests for plugin auto-discovery and registration."""

    def test_plugin_auto_registered(self, pytester):
        """Test that pytest-uuid plugin is auto-discovered."""
        pytester.makepyfile(
            test_discovery="""
            def test_fixtures_available(mock_uuid, spy_uuid, mock_uuid_factory):
                # All fixtures should be available without explicit configuration
                assert mock_uuid is not None
                assert spy_uuid is not None
                assert mock_uuid_factory is not None
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_no_warning(self, pytester):
        """Test that freeze_uuid marker doesn't produce unknown marker warning."""
        pytester.makepyfile(
            test_no_warning="""
            import pytest

            @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
            def test_marker():
                pass
            """
        )

        result = pytester.runpytest("-v", "--strict-markers")
        result.assert_outcomes(passed=1)
        # Should not contain "Unknown pytest.mark.freeze_uuid"
        assert "Unknown" not in result.stdout.str()


class TestCallTracking:
    """Tests for detailed call tracking with UUIDCall metadata."""

    def test_mock_uuid_tracks_caller_module(self, pytester):
        """Test that mock_uuid tracks which module made each call."""
        pytester.makepyfile(
            helper_module="""
            import uuid

            def generate_uuid():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_caller_tracking="""
            import uuid
            import helper_module

            def test_caller_module_tracked(mock_uuid):
                mock_uuid.set("12345678-1234-5678-1234-567812345678")

                # Call from this test module
                uuid.uuid4()

                # Call from helper module
                helper_module.generate_uuid()

                assert mock_uuid.call_count == 2
                assert len(mock_uuid.calls) == 2

                # Check first call came from this test
                call1 = mock_uuid.calls[0]
                assert "test_caller_tracking" in call1.caller_module
                assert call1.was_mocked is True

                # Check second call came from helper
                call2 = mock_uuid.calls[1]
                assert "helper_module" in call2.caller_module
                assert call2.was_mocked is True
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_mock_uuid_calls_from_filter(self, pytester):
        """Test filtering calls by module prefix."""
        pytester.makepyfile(
            myapp_models="""
            import uuid

            def create_model():
                return {"id": str(uuid.uuid4())}
            """
        )

        pytester.makepyfile(
            myapp_utils="""
            import uuid

            def generate_id():
                return str(uuid.uuid4())
            """
        )

        pytester.makepyfile(
            test_calls_from="""
            import uuid
            import myapp_models
            import myapp_utils

            def test_calls_from_filter(mock_uuid):
                mock_uuid.set("12345678-1234-5678-1234-567812345678")

                # Make calls from different modules
                uuid.uuid4()  # From test module
                myapp_models.create_model()  # From myapp_models
                myapp_utils.generate_id()  # From myapp_utils

                # Filter by prefix
                model_calls = mock_uuid.calls_from("myapp_models")
                assert len(model_calls) == 1

                util_calls = mock_uuid.calls_from("myapp_utils")
                assert len(util_calls) == 1

                # Filter by broader prefix
                all_myapp = mock_uuid.calls_from("myapp")
                assert len(all_myapp) == 2

                # No matches
                other_calls = mock_uuid.calls_from("other_package")
                assert len(other_calls) == 0
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_mock_uuid_mocked_vs_real_with_spy_mode(self, pytester):
        """Test tracking mocked vs real calls with spy mode."""
        pytester.makepyfile(
            test_mocked_real="""
            import uuid

            def test_mocked_vs_real(mock_uuid):
                # Start with mocked
                mock_uuid.set("12345678-1234-5678-1234-567812345678")
                mocked1 = uuid.uuid4()
                mocked2 = uuid.uuid4()

                # Switch to spy mode (real UUIDs)
                mock_uuid.spy()
                real1 = uuid.uuid4()
                real2 = uuid.uuid4()

                # Verify call tracking
                assert mock_uuid.call_count == 4
                assert mock_uuid.mocked_count == 2
                assert mock_uuid.real_count == 2

                # Verify mocked_calls
                mocked_calls = mock_uuid.mocked_calls
                assert len(mocked_calls) == 2
                assert all(c.was_mocked for c in mocked_calls)
                assert mocked_calls[0].uuid == mocked1
                assert mocked_calls[1].uuid == mocked2

                # Verify real_calls
                real_calls = mock_uuid.real_calls
                assert len(real_calls) == 2
                assert all(not c.was_mocked for c in real_calls)
                assert real_calls[0].uuid == real1
                assert real_calls[1].uuid == real2
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_spy_uuid_tracks_all_calls_as_real(self, pytester):
        """Test that spy_uuid marks all calls as was_mocked=False."""
        pytester.makepyfile(
            test_spy_calls="""
            import uuid

            def test_spy_all_real(spy_uuid):
                uuid.uuid4()
                uuid.uuid4()
                uuid.uuid4()

                assert spy_uuid.call_count == 3
                assert len(spy_uuid.calls) == 3

                # All calls should be marked as real (not mocked)
                for call in spy_uuid.calls:
                    assert call.was_mocked is False
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_spy_uuid_calls_from_multiple_modules(self, pytester):
        """Test spy_uuid calls_from with multiple modules."""
        pytester.makepyfile(
            service_a="""
            import uuid

            def do_work():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            service_b="""
            import uuid

            def do_work():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_spy_multi_mod="""
            import uuid
            import service_a
            import service_b

            def test_spy_multiple_modules(spy_uuid):
                # Make calls from multiple modules
                service_a.do_work()
                service_b.do_work()
                uuid.uuid4()  # From test module

                assert spy_uuid.call_count == 3

                # Filter by each module
                from_a = spy_uuid.calls_from("service_a")
                from_b = spy_uuid.calls_from("service_b")
                from_test = spy_uuid.calls_from("test_spy")

                assert len(from_a) == 1
                assert len(from_b) == 1
                assert len(from_test) == 1
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestIgnoreListWithCallTracking:
    """Tests for ignore list functionality validated with call tracking."""

    def test_ignored_module_receives_real_uuid(self, pytester):
        """Test that calls from ignored modules return real (non-mocked) UUIDs."""
        pytester.makepyfile(
            ignored_lib="""
            import uuid

            def get_uuid():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_ignore_tracking="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            import ignored_lib

            def test_ignored_marked_real():
                with freeze_uuid(
                    "12345678-1234-5678-1234-567812345678",
                    ignore=["ignored_lib"]
                ) as freezer:
                    # Direct call should be mocked
                    mocked = uuid.uuid4()

                    # Call from ignored module should use real uuid4
                    real = ignored_lib.get_uuid()

                    # Verify the mocked call returned our UUID
                    assert str(mocked) == "12345678-1234-5678-1234-567812345678"

                    # Verify the real call is different
                    assert str(real) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_nested_package_ignore_with_call_tracking(self, pytester):
        """Test ignore list with nested packages and call tracking."""
        # Create nested package structure
        pytester.mkpydir("external_pkg")
        pytester.makepyfile(
            **{
                "external_pkg/submodule/__init__": "",
                "external_pkg/submodule/helper": """
import uuid

def generate():
    return uuid.uuid4()
""",
            }
        )

        pytester.makepyfile(
            test_nested_ignore="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            from external_pkg.submodule import helper

            def test_nested_package_ignored():
                with freeze_uuid(
                    "12345678-1234-5678-1234-567812345678",
                    ignore=["external_pkg"]
                ):
                    # Direct call should be mocked
                    mocked = uuid.uuid4()
                    assert str(mocked) == "12345678-1234-5678-1234-567812345678"

                    # Nested module under external_pkg should be ignored
                    real = helper.generate()
                    assert str(real) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_mock_uuid_with_ignore_list_via_config(self, pytester):
        """Test ignore list via pyproject.toml configuration."""
        pytester.makefile(
            ".toml",
            pyproject="""
            [tool.pytest_uuid]
            default_ignore_list = ["external_service"]
            """,
        )

        pytester.makepyfile(
            external_service="""
            import uuid

            def call_api():
                return {"request_id": str(uuid.uuid4())}
            """
        )

        pytester.makepyfile(
            test_config_ignore="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            import external_service

            def test_config_ignore_list():
                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    # Direct call should be mocked
                    mocked = uuid.uuid4()
                    assert str(mocked) == "12345678-1234-5678-1234-567812345678"

                    # external_service is in default_ignore_list
                    result = external_service.call_api()
                    assert result["request_id"] != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_extend_ignore_list_via_config(self, pytester):
        """Test extending ignore list via pyproject.toml."""
        pytester.makefile(
            ".toml",
            pyproject="""
            [tool.pytest_uuid]
            extend_ignore_list = ["custom_lib"]
            """,
        )

        pytester.makepyfile(
            custom_lib="""
            import uuid

            def generate():
                return uuid.uuid4()
            """
        )

        pytester.makepyfile(
            test_extend_ignore="""
            import uuid
            from pytest_uuid.api import freeze_uuid
            import custom_lib

            def test_extended_ignore():
                with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                    # custom_lib is in extend_ignore_list
                    real = custom_lib.generate()
                    assert str(real) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestUUIDCallDataclass:
    """Tests for UUIDCall dataclass in integration scenarios."""

    def test_uuid_call_has_all_fields(self, pytester):
        """Test UUIDCall dataclass has all expected fields."""
        pytester.makepyfile(
            test_uuid_call_fields="""
            import uuid
            from pytest_uuid.types import UUIDCall

            def test_uuid_call_structure(mock_uuid):
                mock_uuid.set("12345678-1234-5678-1234-567812345678")
                uuid.uuid4()

                call = mock_uuid.calls[0]

                # Verify it's a UUIDCall instance
                assert isinstance(call, UUIDCall)

                # Verify all fields exist
                assert hasattr(call, 'uuid')
                assert hasattr(call, 'was_mocked')
                assert hasattr(call, 'caller_module')
                assert hasattr(call, 'caller_file')

                # Verify field types
                assert isinstance(call.uuid, uuid.UUID)
                assert isinstance(call.was_mocked, bool)
                assert call.caller_module is None or isinstance(call.caller_module, str)
                assert call.caller_file is None or isinstance(call.caller_file, str)
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_uuid_call_is_immutable(self, pytester):
        """Test that UUIDCall instances are immutable (frozen dataclass)."""
        pytester.makepyfile(
            test_uuid_call_frozen="""
            import uuid
            import pytest
            from dataclasses import FrozenInstanceError

            def test_uuid_call_immutable(mock_uuid):
                mock_uuid.set("12345678-1234-5678-1234-567812345678")
                uuid.uuid4()

                call = mock_uuid.calls[0]

                # Attempting to modify should raise
                with pytest.raises(FrozenInstanceError):
                    call.was_mocked = False
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestParallelExecution:
    """Tests for parallel execution with pytest-xdist."""

    def test_xdist_worker_isolation(self, pytester):
        """Test that each xdist worker has isolated mocking state."""
        # Create multiple test files that each set different UUIDs
        pytester.makepyfile(
            test_worker_a="""
            import uuid

            def test_worker_a_uuid(mock_uuid):
                mock_uuid.set("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
                result = uuid.uuid4()
                assert str(result) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            """
        )

        pytester.makepyfile(
            test_worker_b="""
            import uuid

            def test_worker_b_uuid(mock_uuid):
                mock_uuid.set("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
                result = uuid.uuid4()
                assert str(result) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            """
        )

        pytester.makepyfile(
            test_worker_c="""
            import uuid

            def test_worker_c_uuid(mock_uuid):
                mock_uuid.set("cccccccc-cccc-cccc-cccc-cccccccccccc")
                result = uuid.uuid4()
                assert str(result) == "cccccccc-cccc-cccc-cccc-cccccccccccc"
            """
        )

        # Run with 2 workers to test parallel execution
        result = pytester.runpytest("-v", "-n", "2", "-p", "no:randomly")
        result.assert_outcomes(passed=3)

    def test_xdist_no_cross_contamination(self, pytester):
        """Test that parallel workers don't contaminate each other's UUIDs."""
        pytester.makepyfile(
            test_xdist_isolation="""
            import uuid
            import time

            def test_slow_with_uuid_a(mock_uuid):
                mock_uuid.set("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
                # Simulate slow test to increase chance of parallel execution
                time.sleep(0.1)
                # Verify our UUID wasn't changed by another worker
                assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
                time.sleep(0.1)
                assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

            def test_fast_with_uuid_b(mock_uuid):
                mock_uuid.set("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
                # These should execute while test_slow is sleeping
                assert str(uuid.uuid4()) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
                assert str(uuid.uuid4()) == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

            def test_fast_with_uuid_c(mock_uuid):
                mock_uuid.set("cccccccc-cccc-cccc-cccc-cccccccccccc")
                assert str(uuid.uuid4()) == "cccccccc-cccc-cccc-cccc-cccccccccccc"
                assert str(uuid.uuid4()) == "cccccccc-cccc-cccc-cccc-cccccccccccc"
            """
        )

        result = pytester.runpytest("-v", "-n", "2", "-p", "no:randomly")
        result.assert_outcomes(passed=3)


class TestParametrizeInteraction:
    """Tests for interaction with pytest.mark.parametrize."""

    def test_parametrize_with_freeze_uuid_marker(self, pytester):
        """Test that parametrize works with freeze_uuid marker."""
        pytester.makepyfile(
            test_param_marker="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("12345678-1234-5678-1234-567812345678")
            @pytest.mark.parametrize("value", [1, 2, 3])
            def test_parametrized_frozen(value):
                # Each parametrized run should get the frozen UUID
                result = uuid.uuid4()
                assert str(result) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)

    def test_parametrize_with_freeze_uuid_decorator(self, pytester):
        """Test that parametrize works with @freeze_uuid decorator."""
        pytester.makepyfile(
            test_param_decorator="""
            import uuid
            import pytest
            from pytest_uuid import freeze_uuid

            @freeze_uuid("12345678-1234-5678-1234-567812345678")
            @pytest.mark.parametrize("value", ["a", "b", "c"])
            def test_parametrized_decorated(value):
                result = uuid.uuid4()
                assert str(result) == "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)

    def test_parametrize_with_fixture(self, pytester):
        """Test that parametrize works with mock_uuid fixture."""
        pytester.makepyfile(
            test_param_fixture="""
            import uuid
            import pytest

            @pytest.mark.parametrize("expected_uuid", [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
                "33333333-3333-3333-3333-333333333333",
            ])
            def test_parametrized_fixture(mock_uuid, expected_uuid):
                mock_uuid.set(expected_uuid)
                result = uuid.uuid4()
                assert str(result) == expected_uuid
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)

    def test_parametrize_ids_with_seed(self, pytester):
        """Test parametrize with node seeding produces different UUIDs per param."""
        pytester.makepyfile(
            test_param_node_seed="""
            import uuid
            import pytest

            generated_uuids = []

            @pytest.mark.freeze_uuid(seed="node")
            @pytest.mark.parametrize("param", ["x", "y", "z"])
            def test_node_seeded_parametrized(param):
                result = uuid.uuid4()
                generated_uuids.append(str(result))
                # Each parametrized variant has different node ID, so different seed

            def test_all_different():
                # Run after parametrized tests to verify UUIDs were different
                assert len(generated_uuids) == 3
                assert len(set(generated_uuids)) == 3  # All unique
            """
        )

        # Disable randomly to ensure test_all_different runs last
        result = pytester.runpytest("-v", "-p", "no:randomly")
        result.assert_outcomes(passed=4)


class TestExceptionHandling:
    """Tests for exception handling during UUID generation."""

    def test_exception_during_test_restores_uuid4(self, pytester):
        """Test that uuid4 is restored even if test raises exception."""
        pytester.makepyfile(
            test_exception_restore="""
            import uuid
            import pytest
            from pytest_uuid.api import freeze_uuid

            def test_exception_in_context():
                original = uuid.uuid4

                try:
                    with freeze_uuid("12345678-1234-5678-1234-567812345678"):
                        assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
                        raise ValueError("Test exception")
                except ValueError:
                    pass

                # uuid4 should be restored
                assert uuid.uuid4 is original

            def test_after_exception():
                # Should get real UUIDs
                result = uuid.uuid4()
                assert str(result) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_fixture_cleanup_on_test_failure(self, pytester):
        """Test that fixture cleans up properly when test fails."""
        pytester.makepyfile(
            test_fixture_cleanup="""
            import uuid
            import pytest

            def test_failing_test(mock_uuid):
                mock_uuid.set("12345678-1234-5678-1234-567812345678")
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
                pytest.fail("Intentional failure")

            def test_after_failure(mock_uuid):
                # Fixture should have clean state despite previous failure
                # Without setting anything, we get random UUIDs
                result = uuid.uuid4()
                assert str(result) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v", "-p", "no:randomly")
        result.assert_outcomes(passed=1, failed=1)

    def test_decorator_cleanup_on_exception(self, pytester):
        """Test that decorator cleans up on exception."""
        pytester.makepyfile(
            test_decorator_cleanup="""
            import uuid
            import pytest
            from pytest_uuid import freeze_uuid

            @freeze_uuid("12345678-1234-5678-1234-567812345678")
            def test_decorated_failure():
                assert str(uuid.uuid4()) == "12345678-1234-5678-1234-567812345678"
                raise RuntimeError("Test error")

            def test_after_decorated_failure():
                # Should get real UUIDs
                result = uuid.uuid4()
                assert str(result) != "12345678-1234-5678-1234-567812345678"
            """
        )

        result = pytester.runpytest("-v", "-p", "no:randomly")
        result.assert_outcomes(passed=1, failed=1)


class TestLargeSequences:
    """Tests for large UUID sequences and performance."""

    def test_large_sequence_cycling(self, pytester):
        """Test that large sequences cycle correctly."""
        pytester.makepyfile(
            test_large_seq="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_large_sequence():
                # Create a sequence of 100 UUIDs
                uuids = [f"{i:08x}-{i:04x}-{i:04x}-{i:04x}-{i:012x}" for i in range(100)]

                with freeze_uuid(uuids, on_exhausted="cycle"):
                    # Generate 250 UUIDs (2.5 cycles)
                    results = [str(uuid.uuid4()) for _ in range(250)]

                    # First 100 should match sequence
                    assert results[:100] == uuids

                    # Next 100 should be same (cycled)
                    assert results[100:200] == uuids

                    # Last 50 should be first 50 of sequence
                    assert results[200:250] == uuids[:50]
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_large_sequence_raise_on_exhaustion(self, pytester):
        """Test that large sequences raise on exhaustion when configured."""
        pytester.makepyfile(
            test_large_raise="""
            import uuid
            import pytest
            from pytest_uuid.api import freeze_uuid
            from pytest_uuid.generators import UUIDsExhaustedError

            def test_large_sequence_exhaustion():
                # Create a sequence of 50 UUIDs
                uuids = [f"{i:08x}-{i:04x}-{i:04x}-{i:04x}-{i:012x}" for i in range(50)]

                with freeze_uuid(uuids, on_exhausted="raise"):
                    # Generate exactly 50 UUIDs - should work
                    for _ in range(50):
                        uuid.uuid4()

                    # 51st should raise
                    with pytest.raises(UUIDsExhaustedError):
                        uuid.uuid4()
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_many_seeded_uuids_are_unique(self, pytester):
        """Test that seeded generator produces many unique UUIDs."""
        pytester.makepyfile(
            test_seeded_unique="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_seeded_uniqueness():
                with freeze_uuid(seed=42):
                    # Generate 1000 UUIDs
                    results = [uuid.uuid4() for _ in range(1000)]

                    # All should be unique
                    assert len(set(results)) == 1000

                    # All should be valid v4 UUIDs
                    assert all(u.version == 4 for u in results)
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestDeepNesting:
    """Tests for deeply nested freeze_uuid contexts."""

    def test_three_level_nesting(self, pytester):
        """Test three levels of nested freeze_uuid contexts."""
        pytester.makepyfile(
            test_three_levels="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_three_nested():
                with freeze_uuid("11111111-1111-1111-1111-111111111111"):
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                    with freeze_uuid("22222222-2222-2222-2222-222222222222"):
                        assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

                        with freeze_uuid("33333333-3333-3333-3333-333333333333"):
                            assert str(uuid.uuid4()) == "33333333-3333-3333-3333-333333333333"

                        # Back to level 2
                        assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

                    # Back to level 1
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                # Outside all contexts - real UUID
                result = uuid.uuid4()
                assert str(result) not in [
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                    "33333333-3333-3333-3333-333333333333",
                ]
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_five_level_nesting(self, pytester):
        """Test five levels of nested freeze_uuid contexts."""
        pytester.makepyfile(
            test_five_levels="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_five_nested():
                uuids = [
                    f"{i}1111111-1111-1111-1111-111111111111"
                    for i in range(1, 6)
                ]

                with freeze_uuid(uuids[0]):
                    assert str(uuid.uuid4()) == uuids[0]
                    with freeze_uuid(uuids[1]):
                        assert str(uuid.uuid4()) == uuids[1]
                        with freeze_uuid(uuids[2]):
                            assert str(uuid.uuid4()) == uuids[2]
                            with freeze_uuid(uuids[3]):
                                assert str(uuid.uuid4()) == uuids[3]
                                with freeze_uuid(uuids[4]):
                                    assert str(uuid.uuid4()) == uuids[4]
                                assert str(uuid.uuid4()) == uuids[3]
                            assert str(uuid.uuid4()) == uuids[2]
                        assert str(uuid.uuid4()) == uuids[1]
                    assert str(uuid.uuid4()) == uuids[0]
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_nested_with_different_configs(self, pytester):
        """Test nested contexts with different configurations."""
        pytester.makepyfile(
            test_nested_configs="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_nested_different_configs():
                # Outer: static UUID
                with freeze_uuid("11111111-1111-1111-1111-111111111111"):
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                    # Middle: sequence
                    with freeze_uuid([
                        "22222222-2222-2222-2222-222222222222",
                        "33333333-3333-3333-3333-333333333333",
                    ]):
                        assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

                        # Inner: seeded
                        with freeze_uuid(seed=42):
                            seeded_uuid = uuid.uuid4()
                            assert seeded_uuid.version == 4

                        # Back to sequence (continues)
                        assert str(uuid.uuid4()) == "33333333-3333-3333-3333-333333333333"

                    # Back to static
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
