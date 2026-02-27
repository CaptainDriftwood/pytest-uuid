"""Integration tests for pytest markers and hooks.

These tests verify @pytest.mark.freeze_uuid marker functionality
and pytest plugin hook behavior in isolated test environments.
"""

from __future__ import annotations

# --- Pytest hooks ---


def test_marker_registered(pytester):
    """Test that freeze_uuid marker is registered."""
    pytester.makepyfile(
        test_marker_reg="""
        import pytest

        @pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_with_marker():
            pass
        """
    )

    # Run with --markers to check registration
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*freeze_uuid*"])


def test_marker_applies_freezer(pytester):
    """Test that @pytest.mark.freeze_uuid applies the freezer."""
    pytester.makepyfile(
        test_marker_apply="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_marker_works():
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_with_seed_node(pytester):
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


def test_marker_node_seed_distinct_sequences_per_test(pytester):
    """Test that separate tests with seed='node' get distinct UUID sequences.

    Each test function has a unique node ID (e.g., test_module.py::test_one),
    so each should generate a different sequence of UUIDs even when run
    in the same session.
    """
    pytester.makepyfile(
        test_node_distinct="""
        import uuid
        import pytest

        # Collect UUIDs from each test to compare afterward
        collected_uuids = {}

        @pytest.mark.freeze_uuid(seed="node")
        def test_first():
            # Generate a few UUIDs
            uuids = [uuid.uuid4() for _ in range(3)]
            collected_uuids["first"] = [str(u) for u in uuids]

        @pytest.mark.freeze_uuid(seed="node")
        def test_second():
            # Generate the same number of UUIDs
            uuids = [uuid.uuid4() for _ in range(3)]
            collected_uuids["second"] = [str(u) for u in uuids]

        @pytest.mark.freeze_uuid(seed="node")
        def test_third():
            # Generate UUIDs for this test too
            uuids = [uuid.uuid4() for _ in range(3)]
            collected_uuids["third"] = [str(u) for u in uuids]

        def test_verify_all_distinct():
            # This test runs last and verifies all sequences were different
            assert len(collected_uuids) == 3, "All node-seeded tests should have run"

            first_seq = collected_uuids["first"]
            second_seq = collected_uuids["second"]
            third_seq = collected_uuids["third"]

            # Each test should have generated different UUIDs
            assert first_seq != second_seq, "test_first and test_second should differ"
            assert second_seq != third_seq, "test_second and test_third should differ"
            assert first_seq != third_seq, "test_first and test_third should differ"

            # Verify no UUID appears in multiple sequences
            all_uuids = first_seq + second_seq + third_seq
            assert len(set(all_uuids)) == 9, "All 9 UUIDs should be unique"
        """
    )

    # Disable randomly to ensure test_verify_all_distinct runs last
    result = pytester.runpytest("-v", "-p", "no:randomly")
    result.assert_outcomes(passed=4)


def test_marker_cleanup_on_teardown(pytester):
    """Test that marker properly cleans up after test."""
    pytester.makepyfile(
        test_cleanup="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("11111111-1111-4111-8111-111111111111")
        def test_first():
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

        def test_second():
            # Should not be affected by previous test's marker
            result = uuid.uuid4()
            assert str(result) != "11111111-1111-4111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_marker_config_loaded_from_pyproject(pytester):
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
            with freeze_uuid(["11111111-1111-4111-8111-111111111111"]):
                uuid.uuid4()  # First call OK
                with pytest.raises(UUIDsExhaustedError):
                    uuid.uuid4()  # Should raise
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Marker variants ---


def test_marker_with_static_uuid(pytester):
    """Test marker with a static UUID string."""
    pytester.makepyfile(
        test_static="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_static_uuid():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_with_sequence(pytester):
    """Test marker with a UUID sequence."""
    pytester.makepyfile(
        test_sequence="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid(
            [
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
            ],
            on_exhausted="cycle",
        )
        def test_sequence():
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
            assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
            # Cycles back
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_with_integer_seed(pytester):
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


def test_marker_with_on_exhausted_raise(pytester):
    """Test marker with on_exhausted='raise'."""
    pytester.makepyfile(
        test_exhaust="""
        import uuid
        import pytest
        from pytest_uuid.generators import UUIDsExhaustedError

        @pytest.mark.freeze_uuid(
            ["11111111-1111-4111-8111-111111111111"],
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


def test_marker_on_class(pytester):
    """Test marker applied to a test class."""
    pytester.makepyfile(
        test_class_marker="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
        class TestWithMarker:
            def test_one(self):
                assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

            def test_two(self):
                assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_marker_seed_reproducibility(pytester):
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


def test_marker_multiple_on_same_test(pytester):
    """Test multiple @pytest.mark.freeze_uuid markers on the same test."""
    pytester.makepyfile(
        test_multi_marker="""
        import uuid
        import pytest

        # When multiple markers are applied, get_closest_marker returns
        # the innermost one (closest to the function definition)
        @pytest.mark.freeze_uuid("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        @pytest.mark.freeze_uuid("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
        def test_multiple_markers():
            # The inner marker (closest to def) takes precedence
            result = str(uuid.uuid4())
            assert result == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_on_class_and_method(pytester):
    """Test marker on both class and method - method should take precedence."""
    pytester.makepyfile(
        test_class_method_marker="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("11111111-1111-4111-8111-111111111111")
        class TestWithClassMarker:
            def test_class_marker_only(self):
                # Uses class marker
                assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

            @pytest.mark.freeze_uuid("22222222-2222-4222-8222-222222222222")
            def test_method_marker_overrides(self):
                # Method marker should take precedence over class marker
                assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_marker_with_mock_uuid_fixture_override(pytester):
    """Test that fixture can override marker UUID."""
    pytester.makepyfile(
        test_marker_fixture_override="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        def test_fixture_overrides_marker(mock_uuid):
            # First call uses marker's UUID
            first = str(uuid.uuid4())
            assert first == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

            # Fixture can override to a different UUID
            mock_uuid.uuid4.set("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")
            second = str(uuid.uuid4())
            assert second == "bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_with_sequence_exhaustion_and_fixture(pytester):
    """Test marker with sequence that exhausts, then fixture continues."""
    pytester.makepyfile(
        test_sequence_exhaustion="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid(
            [
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
            ],
            on_exhausted="cycle"
        )
        def test_sequence_cycles(mock_uuid):
            # Consume the sequence
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
            assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
            # Cycles back
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

            # But fixture can still override
            mock_uuid.uuid4.set("33333333-3333-4333-8333-333333333333")
            assert str(uuid.uuid4()) == "33333333-3333-4333-8333-333333333333"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_with_uuids_keyword_argument(pytester):
    """Test marker using the uuids keyword argument instead of positional."""
    pytester.makepyfile(
        test_uuids_kwarg="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid(uuids="12345678-1234-4678-8234-567812345678")
        def test_uuids_keyword():
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
            assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_with_uuids_keyword_sequence(pytester):
    """Test marker using uuids keyword with a sequence."""
    pytester.makepyfile(
        test_uuids_kwarg_seq="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid(
            uuids=[
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
            ],
            on_exhausted="cycle"
        )
        def test_uuids_keyword_sequence():
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
            assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
            # Cycles back
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# =============================================================================
# Version-specific markers
# =============================================================================


def test_marker_freeze_uuid4_registered(pytester):
    """Test that freeze_uuid4 marker is registered."""
    result = pytester.runpytest("--markers")
    result.stdout.fnmatch_lines(["*freeze_uuid4*"])


def test_marker_freeze_uuid4_applies_freezer(pytester):
    """Test that @pytest.mark.freeze_uuid4 applies the freezer."""
    pytester.makepyfile(
        test_marker_uuid4="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid4("12345678-1234-4678-8234-567812345678")
        def test_marker_uuid4_works():
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid1_applies_freezer(pytester):
    """Test that @pytest.mark.freeze_uuid1 applies the freezer."""
    pytester.makepyfile(
        test_marker_uuid1="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid1("12345678-1234-1678-8234-567812345678")
        def test_marker_uuid1_works():
            result = uuid.uuid1()
            assert str(result) == "12345678-1234-1678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid1_with_seed(pytester):
    """Test that @pytest.mark.freeze_uuid1 with seed works."""
    pytester.makepyfile(
        test_marker_uuid1_seed="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid1(seed=42)
        def test_marker_uuid1_seeded():
            result = uuid.uuid1()
            assert isinstance(result, uuid.UUID)
            assert result.version == 1
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid7_with_seed(pytester):
    """Test that @pytest.mark.freeze_uuid7 with seed works."""
    pytester.makepyfile(
        test_marker_uuid7_seed="""
        import uuid
        import pytest

        try:
            from uuid6 import uuid7 as _uuid7_test
        except ImportError:
            if not hasattr(uuid, 'uuid7'):
                pytest.skip("uuid7 requires Python 3.14+ or uuid6 package")

        from pytest_uuid._compat import uuid7

        @pytest.mark.freeze_uuid7(seed=42)
        def test_marker_uuid7_seeded():
            result = uuid7()
            assert isinstance(result, uuid.UUID)
            assert result.version == 7
        """
    )

    result = pytester.runpytest("-v")
    # Test passes or is skipped (if uuid6 not available)
    assert result.ret in (0, 5)  # 0 = passed, 5 = no tests collected (skip)


def test_marker_stack_uuid4_and_uuid1(pytester):
    """Test stacking freeze_uuid4 and freeze_uuid1 markers."""
    pytester.makepyfile(
        test_stack_markers="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid4("44444444-4444-4444-8444-444444444444")
        @pytest.mark.freeze_uuid1("11111111-1111-1111-8111-111111111111")
        def test_stacked_markers():
            # Both uuid4 and uuid1 should be frozen
            assert str(uuid.uuid4()) == "44444444-4444-4444-8444-444444444444"
            assert str(uuid.uuid1()) == "11111111-1111-1111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid4_cleanup_on_teardown(pytester):
    """Test that freeze_uuid4 marker properly cleans up after test."""
    pytester.makepyfile(
        test_cleanup_uuid4="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid4("11111111-1111-4111-8111-111111111111")
        def test_first():
            assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

        def test_second():
            # Should not be affected by previous test's marker
            result = uuid.uuid4()
            assert str(result) != "11111111-1111-4111-8111-111111111111"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=2)


def test_marker_freeze_uuid_backward_compat(pytester):
    """Test that old freeze_uuid marker still works (backward compatibility)."""
    pytester.makepyfile(
        test_backward_compat="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid("12345678-1234-4678-8234-567812345678")
        def test_backward_compat():
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid1_with_node(pytester):
    """Test that @pytest.mark.freeze_uuid1 with node parameter works."""
    pytester.makepyfile(
        test_marker_uuid1_node="""
        import uuid
        import pytest

        @pytest.mark.freeze_uuid1(seed=42, node=0x123456789ABC)
        def test_marker_uuid1_with_node():
            result = uuid.uuid1()
            assert isinstance(result, uuid.UUID)
            assert result.version == 1
            assert result.node == 0x123456789ABC
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid6_applies_freezer(pytester):
    """Test that @pytest.mark.freeze_uuid6 applies the freezer."""
    pytester.makepyfile(
        test_marker_uuid6="""
        import uuid
        import pytest

        uuid6_mod = pytest.importorskip("uuid6")

        @pytest.mark.freeze_uuid6("12345678-1234-6678-8234-567812345678")
        def test_marker_uuid6_works():
            result = uuid6_mod.uuid6()
            assert str(result) == "12345678-1234-6678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid6_with_seed(pytester):
    """Test that @pytest.mark.freeze_uuid6 with seed works."""
    pytester.makepyfile(
        test_marker_uuid6_seed="""
        import uuid
        import pytest

        uuid6_mod = pytest.importorskip("uuid6")

        @pytest.mark.freeze_uuid6(seed=42)
        def test_marker_uuid6_seeded():
            result = uuid6_mod.uuid6()
            assert isinstance(result, uuid.UUID)
            assert result.version == 6
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid8_applies_freezer(pytester):
    """Test that @pytest.mark.freeze_uuid8 applies the freezer."""
    pytester.makepyfile(
        test_marker_uuid8="""
        import uuid
        import pytest

        uuid6_mod = pytest.importorskip("uuid6")

        @pytest.mark.freeze_uuid8("12345678-1234-8678-8234-567812345678")
        def test_marker_uuid8_works():
            result = uuid6_mod.uuid8()
            assert str(result) == "12345678-1234-8678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


def test_marker_freeze_uuid8_with_seed(pytester):
    """Test that @pytest.mark.freeze_uuid8 with seed works."""
    pytester.makepyfile(
        test_marker_uuid8_seed="""
        import uuid
        import pytest

        uuid6_mod = pytest.importorskip("uuid6")

        @pytest.mark.freeze_uuid8(seed=42)
        def test_marker_uuid8_seeded():
            result = uuid6_mod.uuid8()
            assert isinstance(result, uuid.UUID)
            assert result.version == 8
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
