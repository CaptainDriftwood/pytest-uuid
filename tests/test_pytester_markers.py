"""Integration tests for pytest markers and hooks.

These tests verify @pytest.mark.freeze_uuid marker functionality
and pytest plugin hook behavior in isolated test environments.
"""

from __future__ import annotations


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

    def test_multiple_markers_on_same_test(self, pytester):
        """Test multiple @pytest.mark.freeze_uuid markers on the same test."""
        pytester.makepyfile(
            test_multi_marker="""
            import uuid
            import pytest

            # When multiple markers are applied, get_closest_marker returns
            # the innermost one (closest to the function definition)
            @pytest.mark.freeze_uuid("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
            @pytest.mark.freeze_uuid("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
            def test_multiple_markers():
                # The inner marker (closest to def) takes precedence
                result = str(uuid.uuid4())
                assert result == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_on_class_and_method(self, pytester):
        """Test marker on both class and method - method should take precedence."""
        pytester.makepyfile(
            test_class_method_marker="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("11111111-1111-1111-1111-111111111111")
            class TestWithClassMarker:
                def test_class_marker_only(self):
                    # Uses class marker
                    assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                @pytest.mark.freeze_uuid("22222222-2222-2222-2222-222222222222")
                def test_method_marker_overrides(self):
                    # Method marker should take precedence over class marker
                    assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_marker_with_mock_uuid_fixture_override(self, pytester):
        """Test that fixture can override marker UUID."""
        pytester.makepyfile(
            test_marker_fixture_override="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
            def test_fixture_overrides_marker(mock_uuid):
                # First call uses marker's UUID
                first = str(uuid.uuid4())
                assert first == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

                # Fixture can override to a different UUID
                mock_uuid.set("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
                second = str(uuid.uuid4())
                assert second == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_marker_with_sequence_exhaustion_and_fixture(self, pytester):
        """Test marker with sequence that exhausts, then fixture continues."""
        pytester.makepyfile(
            test_sequence_exhaustion="""
            import uuid
            import pytest

            @pytest.mark.freeze_uuid(
                [
                    "11111111-1111-1111-1111-111111111111",
                    "22222222-2222-2222-2222-222222222222",
                ],
                on_exhausted="cycle"
            )
            def test_sequence_cycles(mock_uuid):
                # Consume the sequence
                assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"
                assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"
                # Cycles back
                assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

                # But fixture can still override
                mock_uuid.set("33333333-3333-3333-3333-333333333333")
                assert str(uuid.uuid4()) == "33333333-3333-3333-3333-333333333333"
            """
        )

        result = pytester.runpytest("-v")
        result.assert_outcomes(passed=1)
