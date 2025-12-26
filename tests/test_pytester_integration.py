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

    def test_nested_freeze_uuid_contexts(self, pytester):
        """Test that nested freeze_uuid contexts work correctly."""
        pytester.makepyfile(
            test_nested="""
            import uuid
            from pytest_uuid.api import freeze_uuid

            def test_nested():
                with freeze_uuid("11111111-1111-1111-1111-111111111111"):
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                    with freeze_uuid("22222222-2222-2222-2222-222222222222"):
                        assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

                    # Outer context restored
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

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

            # Store the UUID from first test to compare
            first_uuid = None

            @pytest.mark.freeze_uuid(seed=12345)
            def test_first():
                global first_uuid
                first_uuid = uuid.uuid4()
                assert first_uuid.version == 4

            @pytest.mark.freeze_uuid(seed=12345)
            def test_second():
                # Same seed should produce same first UUID
                result = uuid.uuid4()
                assert result == first_uuid
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

            generated = []

            def test_first():
                generated.append(uuid.uuid4())

            def test_second():
                generated.append(uuid.uuid4())

            def test_verify():
                # Session scope means sequence continues (not reset per test)
                # So second UUID should be different from first
                assert generated[0] != generated[1]
                assert generated[0].version == 4
                assert generated[1].version == 4
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)

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

        pytester.makepyfile(
            test_mod_a="""
            import uuid

            first_uuid = None

            def test_get_first():
                global first_uuid
                first_uuid = uuid.uuid4()

            def test_check_continues():
                # Within same module, sequence continues
                second = uuid.uuid4()
                assert second != first_uuid
            """
        )

        pytester.makepyfile(
            test_mod_b="""
            import uuid
            import test_mod_a

            def test_module_reset():
                # New module = fresh fixture = sequence restarts
                result = uuid.uuid4()
                # Should equal first UUID from test_mod_a (same seed, reset sequence)
                assert result == test_mod_a.first_uuid
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=3)


class TestPluginDiscovery:
    """Tests for plugin auto-discovery and registration."""

    def test_plugin_auto_registered(self, pytester):
        """Test that pytest-uuid plugin is auto-discovered."""
        pytester.makepyfile(
            test_discovery="""
            def test_fixtures_available(mock_uuid, spy_uuid, uuid_freezer, mock_uuid_factory):
                # All fixtures should be available without explicit configuration
                assert mock_uuid is not None
                assert spy_uuid is not None
                assert uuid_freezer is not None
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
