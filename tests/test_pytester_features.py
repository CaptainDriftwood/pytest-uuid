"""Integration tests for pytest-uuid features.

These tests verify spy functionality, plugin discovery, call tracking,
parallel execution, and parametrize interaction.
"""

from __future__ import annotations


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
