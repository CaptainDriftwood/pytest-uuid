"""Integration tests for edge cases and error handling.

These tests cover ignore lists, direct import patching, exception handling,
large sequences, and deeply nested contexts.
"""

from __future__ import annotations

# --- Ignore list functionality ---


def test_ignore_list_ignored_module_gets_real_uuid(pytester):
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
                "12345678-1234-4678-8234-567812345678",
                ignore=["ignored_helper"]
            ):
                # Direct call should be mocked
                mocked = uuid.uuid4()
                assert str(mocked) == "12345678-1234-4678-8234-567812345678"

                # Call from ignored module should be real (different)
                real = ignored_helper.get_uuid()
                assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_list_non_ignored_module_gets_mocked_uuid(pytester):
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
            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                # Both should be mocked
                direct = uuid.uuid4()
                from_helper = helper.get_uuid()

                assert str(direct) == "12345678-1234-4678-8234-567812345678"
                assert str(from_helper) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_list_multiple_prefixes(pytester):
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
                "12345678-1234-4678-8234-567812345678",
                ignore=["pkg_a", "pkg_b"]
            ):
                # Direct call should be mocked
                direct = uuid.uuid4()
                assert str(direct) == "12345678-1234-4678-8234-567812345678"

                # Both ignored modules should get real UUIDs
                from_a = pkg_a.get_uuid()
                from_b = pkg_b.get_uuid()

                assert str(from_a) != "12345678-1234-4678-8234-567812345678"
                assert str(from_b) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_list_with_sequence(pytester):
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
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
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


def test_ignore_list_nested_module_matching(pytester):
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
                "12345678-1234-4678-8234-567812345678",
                ignore=["mypkg.subpkg"]
            ):
                # Direct call should be mocked
                mocked = uuid.uuid4()
                assert str(mocked) == "12345678-1234-4678-8234-567812345678"

                # Nested module should get real UUID
                real = helper.get_uuid()
                assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_list_mixed_import_patterns(pytester):
    """Test all import patterns together with ignore list."""
    # Create module using `import uuid`
    pytester.makepyfile(
        module_a="""
import uuid

def get_uuid():
    return uuid.uuid4()
"""
    )

    # Create module using `from uuid import uuid4`
    pytester.makepyfile(
        module_b="""
from uuid import uuid4

def get_uuid():
    return uuid4()
"""
    )

    # Create nested package that will be ignored
    pytester.mkpydir("ignored_pkg")
    pytester.makepyfile(
        **{
            "ignored_pkg/sub/__init__": "",
            "ignored_pkg/sub/helper": """
import uuid

def get_uuid():
    return uuid.uuid4()
""",
        }
    )

    pytester.makepyfile(
        test_mixed_patterns="""
        import uuid
        from pytest_uuid.api import freeze_uuid
        import module_a
        import module_b
        from ignored_pkg.sub import helper

        def test_mixed_import_patterns():
            with freeze_uuid(
                "12345678-1234-4678-8234-567812345678",
                ignore=["ignored_pkg"]
            ):
                # Direct call with `import uuid` - should be mocked
                direct = uuid.uuid4()
                assert str(direct) == "12345678-1234-4678-8234-567812345678"

                # module_a uses `import uuid` - should be mocked
                from_module_a = module_a.get_uuid()
                assert str(from_module_a) == "12345678-1234-4678-8234-567812345678"

                # module_b uses `from uuid import uuid4` - should be mocked
                from_module_b = module_b.get_uuid()
                assert str(from_module_b) == "12345678-1234-4678-8234-567812345678"

                # ignored_pkg.sub.helper uses `import uuid` - should be REAL
                from_ignored = helper.get_uuid()
                assert str(from_ignored) != "12345678-1234-4678-8234-567812345678"
                assert isinstance(from_ignored, uuid.UUID)
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_list_decorator_respects_ignore(pytester):
    """Test that @freeze_uuid decorator respects ignore list."""
    pytester.makepyfile(
        ignored_service="""
        import uuid

        def get_request_id():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_decorator_ignore="""
        import uuid
        from pytest_uuid import freeze_uuid
        import ignored_service

        @freeze_uuid("12345678-1234-4678-8234-567812345678", ignore=["ignored_service"])
        def test_decorator_with_ignore():
            # Direct call should be mocked
            mocked = uuid.uuid4()
            assert str(mocked) == "12345678-1234-4678-8234-567812345678"

            # Call from ignored module should be real
            real = ignored_service.get_request_id()
            assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_list_class_decorator_respects_ignore(pytester):
    """Test that @freeze_uuid on class respects ignore list."""
    pytester.makepyfile(
        external_lib="""
        import uuid

        def generate():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_class_decorator_ignore="""
        import uuid
        from pytest_uuid import freeze_uuid
        import external_lib

        @freeze_uuid("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa", ignore=["external_lib"])
        class TestWithIgnore:
            def test_method_one(self):
                # Direct call mocked
                assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
                # Ignored module returns real
                real = external_lib.generate()
                assert str(real) != "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

            def test_method_two(self):
                # Same behavior in another method
                assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
                real = external_lib.generate()
                assert str(real) != "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_ignore_list_decorator_multiple_prefixes(pytester):
    """Test decorator with multiple module prefixes in ignore list."""
    pytester.makepyfile(
        lib_a="""
        import uuid
        def get_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        lib_b="""
        import uuid
        def get_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_multi_ignore_decorator="""
        import uuid
        from pytest_uuid import freeze_uuid
        import lib_a
        import lib_b

        @freeze_uuid("12345678-1234-4678-8234-567812345678", ignore=["lib_a", "lib_b"])
        def test_multiple_ignores():
            # Direct call mocked
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

            # Both ignored modules get real UUIDs
            real_a = lib_a.get_uuid()
            real_b = lib_b.get_uuid()
            assert str(real_a) != "12345678-1234-4678-8234-567812345678"
            assert str(real_b) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Direct import patching ---


def test_direct_import_from_uuid_import_uuid4_is_patched(pytester):
    """Test that 'from uuid import uuid4' is properly patched."""
    pytester.makepyfile(
        test_direct_import="""
        from uuid import uuid4
        from pytest_uuid.api import freeze_uuid

        def test_direct_import_patched():
            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                result = uuid4()
                assert str(result) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_both_styles_in_same_module(pytester):
    """Test both import styles work in the same module."""
    pytester.makepyfile(
        test_both_styles="""
        import uuid
        from uuid import uuid4

        def test_both_import_styles(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")

            # Both should return the mocked UUID
            result1 = uuid.uuid4()
            result2 = uuid4()

            assert str(result1) == "12345678-1234-4678-8234-567812345678"
            assert str(result2) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_multiple_modules(pytester):
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
            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                result_a = module_a.get_uuid()
                result_b = module_b.get_uuid()

                assert str(result_a) == "12345678-1234-4678-8234-567812345678"
                assert str(result_b) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_patching_restored_after_context(pytester):
    """Test that patching is properly restored after context exit."""
    pytester.makepyfile(
        test_restore="""
        import uuid
        from uuid import uuid4 as direct_uuid4
        from pytest_uuid.api import freeze_uuid

        def test_restore_after_context():
            original_module = uuid.uuid4

            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                # Should be mocked
                assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

            # Should be restored
            assert uuid.uuid4 is original_module

            # Should return real UUIDs now
            result = uuid.uuid4()
            assert str(result) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_in_test_file_with_fixture(pytester):
    """Test that direct import in test file itself is patched by mock_uuid."""
    pytester.makepyfile(
        test_direct_in_test="""
        from uuid import uuid4

        def test_direct_import_in_test_file(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")

            # Direct import in THIS test file should be patched
            result = uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_in_test_file_with_marker(pytester):
    """Test that direct import in test file is patched by marker."""
    pytester.makepyfile(
        test_direct_marker="""
        import pytest
        from uuid import uuid4

        @pytest.mark.freeze_uuid("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        def test_direct_import_with_marker():
            # Direct import in THIS test file should be patched
            result = uuid4()
            assert str(result) == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_in_test_file_with_decorator(pytester):
    """Test that direct import in test file is patched by @freeze_uuid."""
    pytester.makepyfile(
        test_direct_decorator="""
        from uuid import uuid4
        from pytest_uuid import freeze_uuid

        @freeze_uuid("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
        def test_direct_import_with_decorator():
            # Direct import in THIS test file should be patched
            result = uuid4()
            assert str(result) == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_direct_import_in_test_file_with_context_manager(pytester):
    """Test that direct import in test file is patched by context manager."""
    pytester.makepyfile(
        test_direct_context="""
        from uuid import uuid4
        from pytest_uuid import freeze_uuid

        def test_direct_import_with_context():
            with freeze_uuid("cccccccc-cccc-4ccc-accc-cccccccccccc"):
                # Direct import in THIS test file should be patched
                result = uuid4()
                assert str(result) == "cccccccc-cccc-4ccc-accc-cccccccccccc"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Aliased import patching ---


def test_aliased_import_is_patched(pytester):
    """Test that 'from uuid import uuid4 as alias' is patched."""
    pytester.makepyfile(
        mymodule="""
        from uuid import uuid4 as generate_id

        def create_entity():
            return str(generate_id())
        """
    )

    pytester.makepyfile(
        test_alias="""
        import mymodule

        def test_aliased_import(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            result = mymodule.create_entity()
            assert result == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_aliased_import_with_freeze_uuid_decorator(pytester):
    """Test that aliased imports are patched by @freeze_uuid decorator."""
    pytester.makepyfile(
        helper="""
        from uuid import uuid4 as make_uuid

        def get_id():
            return str(make_uuid())
        """
    )

    pytester.makepyfile(
        test_alias_decorator="""
        from pytest_uuid import freeze_uuid
        import helper

        @freeze_uuid("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        def test_aliased_import_with_decorator():
            result = helper.get_id()
            assert result == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_aliased_import_in_test_file(pytester):
    """Test that aliased import in the test file itself is patched."""
    pytester.makepyfile(
        test_alias_in_test="""
        from uuid import uuid4 as my_uuid

        def test_aliased_import_in_test_file(mock_uuid):
            mock_uuid.uuid4.set("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
            result = my_uuid()
            assert str(result) == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_multiple_aliases_same_module(pytester):
    """Test that multiple aliases in the same module are all patched."""
    pytester.makepyfile(
        multi_alias="""
        from uuid import uuid4 as id1
        from uuid import uuid4 as id2
        from uuid import uuid4  # standard import too

        def get_ids():
            return str(id1()), str(id2()), str(uuid4())
        """
    )

    pytester.makepyfile(
        test_multi_alias="""
        import multi_alias

        def test_multiple_aliases(mock_uuid):
            mock_uuid.uuid4.set("cccccccc-cccc-4ccc-accc-cccccccccccc")
            a, b, c = multi_alias.get_ids()
            assert a == "cccccccc-cccc-4ccc-accc-cccccccccccc"
            assert b == "cccccccc-cccc-4ccc-accc-cccccccccccc"
            assert c == "cccccccc-cccc-4ccc-accc-cccccccccccc"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_module_alias_import_uuid_as_alias(pytester):
    """Test that 'import uuid as my_uuid' is patched.

    This works because module aliasing still references the same module object,
    so patching uuid.uuid4 automatically affects my_uuid.uuid4.
    """
    pytester.makepyfile(
        mymodule="""
        import uuid as my_uuid

        def create_id():
            return str(my_uuid.uuid4())
        """
    )

    pytester.makepyfile(
        test_module_alias="""
        import mymodule

        def test_module_alias(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            result = mymodule.create_id()
            assert result == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_module_alias_in_test_file(pytester):
    """Test that 'import uuid as alias' in test file itself is patched."""
    pytester.makepyfile(
        test_alias_in_test="""
        import uuid as u

        def test_module_alias_in_test(mock_uuid):
            mock_uuid.uuid4.set("dddddddd-dddd-4ddd-addd-dddddddddddd")
            result = u.uuid4()
            assert str(result) == "dddddddd-dddd-4ddd-addd-dddddddddddd"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Edge cases and error handling ---


def test_edge_case_mock_uuid_and_spy_uuid_mutual_exclusion(pytester):
    """Test that accessing mock_uuid.uuid4 with spy_uuid active raises UsageError."""
    pytester.makepyfile(
        test_both_fixtures="""
        def test_both_fixtures(mock_uuid, spy_uuid):
            # Accessing mock_uuid.uuid4 while spy_uuid is active should fail
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Cannot use both 'mock_uuid.uuid4' and 'spy_uuid'*"])


def test_edge_case_spy_uuid_and_mock_uuid_mutual_exclusion(pytester):
    """Test mutual exclusion works regardless of fixture order."""
    pytester.makepyfile(
        test_both_fixtures_reversed="""
        def test_both_fixtures(spy_uuid, mock_uuid):
            # Accessing mock_uuid.uuid4 while spy_uuid is active should fail
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*Cannot use both 'mock_uuid.uuid4' and 'spy_uuid'*"])


def test_edge_case_mock_uuid_and_spy_uuid_coexist_for_different_versions(pytester):
    """Test that mock_uuid and spy_uuid can coexist for different UUID versions."""
    pytester.makepyfile(
        test_coexist="""
        import uuid

        def test_different_uuid_versions(mock_uuid, spy_uuid):
            # spy_uuid tracks uuid4
            # mock_uuid.uuid1 mocks uuid1 - no conflict!
            mock_uuid.uuid1.set("12345678-1234-1234-8234-567812345678")

            # uuid4 goes through spy
            result4 = uuid.uuid4()
            assert spy_uuid.call_count == 1

            # uuid1 goes through mock
            result1 = uuid.uuid1()
            assert str(result1) == "12345678-1234-1234-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_edge_case_mock_uuid_spy_method_works(pytester):
    """Test that mock_uuid.uuid4.spy() is the correct alternative."""
    pytester.makepyfile(
        test_spy_method="""
        import uuid

        def test_mock_uuid_spy_mode(mock_uuid):
            mock_uuid.uuid4.spy()  # Switch to spy mode

            result = uuid.uuid4()

            assert mock_uuid.uuid4.call_count == 1
            assert mock_uuid.uuid4.last_uuid == result
            # Real UUID, so version should be 4
            assert result.version == 4
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_edge_case_marker_and_fixture_together(pytester):
    """Test using marker and fixture in the same test."""
    pytester.makepyfile(
        test_marker_fixture="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("11111111-1111-4111-8111-111111111111")
        def test_marker_with_fixture(mock_uuid):
            # Marker should already be applied
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

            # Fixture can override
            mock_uuid.uuid4.set("22222222-2222-4222-8222-222222222222")
            assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_edge_case_exhaustion_raise_behavior(pytester):
    """Test that exhaustion with 'raise' behavior works."""
    pytester.makepyfile(
        test_exhaust_raise="""
        import uuid
        import pytest
        from pytest_uuid.api import freeze_uuid
        from pytest_uuid.generators import UUIDsExhaustedError

        def test_raise_on_exhausted():
            with freeze_uuid(
                ["11111111-1111-4111-8111-111111111111"],
                on_exhausted="raise"
            ):
                uuid.uuid4()  # OK
                with pytest.raises(UUIDsExhaustedError):
                    uuid.uuid4()  # Should raise
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_edge_case_seeded_reproducibility_across_runs(pytester):
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


def test_edge_case_invalid_exhaustion_behavior_raises(pytester):
    """Test that invalid exhaustion behavior string raises ValueError."""
    pytester.makepyfile(
        test_invalid_exhaust="""
        import pytest
        from pytest_uuid.api import freeze_uuid

        def test_invalid_exhaustion():
            with pytest.raises(ValueError):
                with freeze_uuid(
                    ["11111111-1111-4111-8111-111111111111"],
                    on_exhausted="invalid_behavior"
                ):
                    pass
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Ignore list with call tracking ---


def test_ignore_tracking_ignored_module_receives_real_uuid(pytester):
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
                "12345678-1234-4678-8234-567812345678",
                ignore=["ignored_lib"]
            ) as freezer:
                # Direct call should be mocked
                mocked = uuid.uuid4()

                # Call from ignored module should use real uuid4
                real = ignored_lib.get_uuid()

                # Verify the mocked call returned our UUID
                assert str(mocked) == "12345678-1234-4678-8234-567812345678"

                # Verify the real call is different
                assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_tracking_nested_package(pytester):
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
                "12345678-1234-4678-8234-567812345678",
                ignore=["external_pkg"]
            ):
                # Direct call should be mocked
                mocked = uuid.uuid4()
                assert str(mocked) == "12345678-1234-4678-8234-567812345678"

                # Nested module under external_pkg should be ignored
                real = helper.generate()
                assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_config_via_pyproject(pytester):
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
            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                # Direct call should be mocked
                mocked = uuid.uuid4()
                assert str(mocked) == "12345678-1234-4678-8234-567812345678"

                # external_service is in default_ignore_list
                result = external_service.call_api()
                assert result["request_id"] != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_config_extend_ignore_list(pytester):
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
            with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                # custom_lib is in extend_ignore_list
                real = custom_lib.generate()
                assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_config_marker_respects_pyproject(pytester):
    """Test that @pytest.mark.freeze_uuid respects pyproject.toml ignore list."""
    pytester.makefile(
        ".toml",
        pyproject="""
        [tool.pytest_uuid]
        default_ignore_list = ["ignored_via_config"]
        """,
    )

    pytester.makepyfile(
        ignored_via_config="""
        import uuid

        def get_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_marker_config_ignore="""
        import uuid
        import pytest
        import ignored_via_config

        @pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_marker_respects_config_ignore():
            # Direct call should be mocked
            mocked = uuid.uuid4()
            assert str(mocked) == "12345678-1234-4678-8234-567812345678"

            # Module in default_ignore_list should get real UUID
            real = ignored_via_config.get_uuid()
            assert str(real) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_ignore_config_marker_extends_ignore_list(pytester):
    """Test that marker respects extend_ignore_list from pyproject.toml."""
    pytester.makefile(
        ".toml",
        pyproject="""
        [tool.pytest_uuid]
        extend_ignore_list = ["extended_lib"]
        """,
    )

    pytester.makepyfile(
        extended_lib="""
        import uuid

        def generate():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_marker_extend_ignore="""
        import uuid
        import pytest
        import extended_lib

        @pytest.mark.freeze_uuid("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        def test_marker_extends_ignore():
            # Direct call mocked
            assert str(uuid.uuid4()) == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

            # extended_lib is in extend_ignore_list
            real = extended_lib.generate()
            assert str(real) != "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Exception handling ---


def test_exception_during_test_restores_uuid4(pytester):
    """Test that uuid4 is restored even if test raises exception."""
    pytester.makepyfile(
        test_exception_restore="""
        import uuid
        import pytest
        from pytest_uuid.api import freeze_uuid

        def test_exception_in_context():
            original = uuid.uuid4

            try:
                with freeze_uuid("12345678-1234-4678-8234-567812345678"):
                    assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # uuid4 should be restored
            assert uuid.uuid4 is original

        def test_after_exception():
            # Should get real UUIDs
            result = uuid.uuid4()
            assert str(result) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_exception_fixture_cleanup_on_test_failure(pytester):
    """Test that fixture cleans up properly when test fails."""
    pytester.makepyfile(
        test_fixture_cleanup="""
        import uuid
        import pytest

        def test_failing_test(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
            pytest.fail("Intentional failure")

        def test_after_failure(mock_uuid):
            # Fixture should have clean state despite previous failure
            # Without setting anything, we get random UUIDs
            result = uuid.uuid4()
            assert str(result) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=1, failed=1)


def test_exception_decorator_cleanup(pytester):
    """Test that decorator cleans up on exception."""
    pytester.makepyfile(
        test_decorator_cleanup="""
        import uuid
        import pytest
        from pytest_uuid import freeze_uuid

        @freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_decorated_failure():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
            raise RuntimeError("Test error")

        def test_after_decorated_failure():
            # Should get real UUIDs
            result = uuid.uuid4()
            assert str(result) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=1, failed=1)


def test_exception_catch_exhausted_error_and_continue(pytester):
    """Test catching UUIDsExhaustedError and continuing within same context."""
    pytester.makepyfile(
        test_catch_continue="""
        import uuid
        import pytest
        from pytest_uuid.api import freeze_uuid
        from pytest_uuid.generators import UUIDsExhaustedError

        def test_catch_and_continue():
            with freeze_uuid(
                ["11111111-1111-4111-8111-111111111111"],
                on_exhausted="raise"
            ) as freezer:
                # First call succeeds
                first = uuid.uuid4()
                assert str(first) == "11111111-1111-4111-8111-111111111111"

                # Second call raises but we catch it
                try:
                    uuid.uuid4()
                    pytest.fail("Should have raised UUIDsExhaustedError")
                except UUIDsExhaustedError as e:
                    assert e.count == 1

                # The context is still active, subsequent calls also raise
                with pytest.raises(UUIDsExhaustedError):
                    uuid.uuid4()
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_exception_catch_exhausted_set_new_uuid(pytester):
    """Test catching UUIDsExhaustedError and setting new UUID via fixture."""
    pytester.makepyfile(
        test_catch_set_new="""
        import uuid
        import pytest
        from pytest_uuid.generators import UUIDsExhaustedError

        @pytest.mark.freeze_uuid(
            ["11111111-1111-4111-8111-111111111111"],
            on_exhausted="raise"
        )
        def test_recover_with_fixture(mock_uuid):
            # First call uses marker's UUID
            first = uuid.uuid4()
            assert str(first) == "11111111-1111-4111-8111-111111111111"

            # Second call raises
            with pytest.raises(UUIDsExhaustedError):
                uuid.uuid4()

            # But fixture can set a new UUID to recover
            mock_uuid.uuid4.set("22222222-2222-4222-8222-222222222222")
            recovered = uuid.uuid4()
            assert str(recovered) == "22222222-2222-4222-8222-222222222222"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_exception_nested_cleanup(pytester):
    """Test cleanup when exception occurs in nested context."""
    pytester.makepyfile(
        test_nested_exc="""
        import uuid
        import pytest
        from pytest_uuid.api import freeze_uuid

        def test_nested_exception():
            with freeze_uuid("11111111-1111-4111-8111-111111111111"):
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

                try:
                    with freeze_uuid("22222222-2222-4222-8222-222222222222"):
                        assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
                        raise ValueError("Inner error")
                except ValueError:
                    pass

                # Outer context should still work
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

            # Outside all contexts
            result = uuid.uuid4()
            assert str(result) != "11111111-1111-4111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Large sequences ---


def test_large_sequence_cycling(pytester):
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


def test_large_sequence_raise_on_exhaustion(pytester):
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


def test_large_sequence_many_seeded_uuids_are_unique(pytester):
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


# --- Deep nesting ---


def test_deep_nesting_three_levels(pytester):
    """Test three levels of nested freeze_uuid contexts."""
    pytester.makepyfile(
        test_three_levels="""
        import uuid
        from pytest_uuid.api import freeze_uuid

        def test_three_nested():
            with freeze_uuid("11111111-1111-4111-8111-111111111111"):
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

                with freeze_uuid("22222222-2222-4222-8222-222222222222"):
                    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"

                    with freeze_uuid("33333333-3333-4333-8333-333333333333"):
                        assert str(uuid.uuid4()) == "33333333-3333-4333-8333-333333333333"

                    # Back to level 2
                    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"

                # Back to level 1
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

            # Outside all contexts - real UUID
            result = uuid.uuid4()
            assert str(result) not in [
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
                "33333333-3333-4333-8333-333333333333",
            ]
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_deep_nesting_five_levels(pytester):
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


def test_deep_nesting_different_configs(pytester):
    """Test nested contexts with different configurations."""
    pytester.makepyfile(
        test_nested_configs="""
        import uuid
        from pytest_uuid.api import freeze_uuid

        def test_nested_different_configs():
            # Outer: static UUID
            with freeze_uuid("11111111-1111-4111-8111-111111111111"):
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

                # Middle: sequence
                with freeze_uuid([
                    "22222222-2222-4222-8222-222222222222",
                    "33333333-3333-4333-8333-333333333333",
                ]):
                    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"

                    # Inner: seeded
                    with freeze_uuid(seed=42):
                        seeded_uuid = uuid.uuid4()
                        assert seeded_uuid.version == 4

                    # Back to sequence (continues)
                    assert str(uuid.uuid4()) == "33333333-3333-4333-8333-333333333333"

                # Back to static
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_nested_contexts_with_module_imports(pytester):
    """Test nested freeze_uuid with modules using 'from uuid import uuid4'.

    This specifically tests that modules with direct uuid4 imports are
    correctly patched and restored through nested contexts.
    """
    pytester.makepyfile(
        uuid_helper="""
from uuid import uuid4

def generate():
    return uuid4()
"""
    )

    pytester.makepyfile(
        test_nested_with_imports="""
import uuid
import uuid_helper
from pytest_uuid.api import freeze_uuid

def test_nested_module_imports():
    # Outer context with seed=1
    with freeze_uuid(seed=1) as outer:
        outer.reset()
        outer_uuid1 = uuid_helper.generate()

        # Inner context with seed=2
        with freeze_uuid(seed=2) as inner:
            inner.reset()
            inner_uuid1 = uuid_helper.generate()

            # Inner should use seed=2, different from outer
            inner.reset()
            inner_uuid2 = uuid_helper.generate()
            assert inner_uuid1 == inner_uuid2, "Inner should be deterministic"

        # After inner exits, outer should still work with seed=1
        outer.reset()
        outer_uuid2 = uuid_helper.generate()
        assert outer_uuid1 == outer_uuid2, "Outer should still be deterministic after inner exits"

    # After all contexts exit, uuid_helper should have true original
    assert uuid_helper.uuid4 is uuid.uuid4, (
        "Module's uuid4 should be restored to true original"
    )
"""
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
