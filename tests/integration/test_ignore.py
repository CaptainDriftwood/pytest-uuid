"""Integration tests for mock_uuid.uuid4.set_ignore() functionality.

These tests verify that the ignore list feature allows certain modules
to receive real UUIDs while others receive mocked UUIDs.
"""

from __future__ import annotations

# --- Ignore single module ---


def test_ignore_single_module(pytester):
    """Test that mock_uuid can ignore a single module."""
    # Create a helper module
    pytester.makepyfile(
        helper="""
        import uuid

        def get_uuid():
            return uuid.uuid4()
        """
    )

    # Create a test that uses set_ignore
    pytester.makepyfile(
        test_ignore="""
        import uuid
        import helper

        def test_ignore_module(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            mock_uuid.uuid4.set_ignore("helper")

            # Direct call should be mocked
            mocked = uuid.uuid4()
            assert str(mocked) == "12345678-1234-4678-8234-567812345678"

            # Call from ignored module should be real
            real = helper.get_uuid()
            assert str(real) != "12345678-1234-4678-8234-567812345678"

            # Verify tracking
            assert mock_uuid.uuid4.mocked_count == 1
            assert mock_uuid.uuid4.real_count == 1
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Ignore multiple modules ---


def test_ignore_multiple_modules(pytester):
    """Test that mock_uuid can ignore multiple modules."""
    # Create two helper modules
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
        test_multiple="""
        import uuid
        import pkg_a
        import pkg_b

        def test_ignore_multiple(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            mock_uuid.uuid4.set_ignore("pkg_a", "pkg_b")

            # Direct call should be mocked
            mocked = uuid.uuid4()
            assert str(mocked) == "12345678-1234-4678-8234-567812345678"

            # Calls from ignored modules should be real
            real_a = pkg_a.get_uuid()
            real_b = pkg_b.get_uuid()

            assert str(real_a) != "12345678-1234-4678-8234-567812345678"
            assert str(real_b) != "12345678-1234-4678-8234-567812345678"
            assert real_a != real_b  # They should be different random UUIDs

            # Verify tracking
            assert mock_uuid.uuid4.mocked_count == 1
            assert mock_uuid.uuid4.real_count == 2
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Dynamic ignore updates ---


def test_ignore_updates_dynamically(pytester):
    """Test that ignore list can be updated during test."""
    pytester.makepyfile(
        helper="""
        import uuid
        def get_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_dynamic="""
        import uuid
        import helper

        def test_dynamic_ignore(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")

            # Initially, helper is not ignored
            uuid1 = helper.get_uuid()
            assert str(uuid1) == "12345678-1234-4678-8234-567812345678"

            # Add helper to ignore list
            mock_uuid.uuid4.set_ignore("helper")

            # Now helper calls should be real
            uuid2 = helper.get_uuid()
            assert str(uuid2) != "12345678-1234-4678-8234-567812345678"

            # Direct calls still mocked
            uuid3 = uuid.uuid4()
            assert str(uuid3) == "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Reset preserves ignore ---


def test_ignore_with_reset(pytester):
    """Test that reset preserves the initial ignore configuration."""
    pytester.makepyfile(
        helper="""
        import uuid
        def get_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_reset="""
        import uuid
        import helper

        def test_reset_preserves_ignore(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            mock_uuid.uuid4.set_ignore("helper")

            # Helper calls should be real
            uuid1 = helper.get_uuid()
            assert str(uuid1) != "12345678-1234-4678-8234-567812345678"

            # Reset the mocker
            mock_uuid.uuid4.reset()
            mock_uuid.uuid4.set("87654321-8765-4321-8765-876543218765")

            # Helper calls should still be real after reset
            uuid2 = helper.get_uuid()
            assert str(uuid2) != "87654321-8765-4321-8765-876543218765"

            # Direct calls should use the new mock value
            uuid3 = uuid.uuid4()
            assert str(uuid3) == "87654321-8765-4321-8765-876543218765"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Nested module calls ---


def test_ignore_with_nested_calls(pytester):
    """Test ignore with nested module calls."""
    pytester.makepyfile(
        base_module="""
        import uuid
        def base_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        wrapper_module="""
        import base_module
        def wrapper_uuid():
            return base_module.base_uuid()
        """
    )

    pytester.makepyfile(
        test_nested="""
        import uuid
        import wrapper_module
        import base_module

        def test_nested_ignore(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            mock_uuid.uuid4.set_ignore("base_module")

            # Direct call should be mocked
            uuid1 = uuid.uuid4()
            assert str(uuid1) == "12345678-1234-4678-8234-567812345678"

            # Call through wrapper, but base_module is in call stack
            uuid2 = wrapper_module.wrapper_uuid()
            assert str(uuid2) != "12345678-1234-4678-8234-567812345678"

            # Direct call to base_module
            uuid3 = base_module.base_uuid()
            assert str(uuid3) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)


# --- Call tracking with ignore ---


def test_calls_tracking_with_ignore(pytester):
    """Test that call tracking distinguishes between mocked and real calls."""
    pytester.makepyfile(
        ignored_module="""
        import uuid
        def get_uuid():
            return uuid.uuid4()
        """
    )

    pytester.makepyfile(
        test_tracking="""
        import uuid
        import ignored_module

        def test_call_tracking(mock_uuid):
            mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
            mock_uuid.uuid4.set_ignore("ignored_module")

            # Make some calls
            uuid1 = uuid.uuid4()  # mocked
            uuid2 = ignored_module.get_uuid()  # real
            uuid3 = uuid.uuid4()  # mocked

            # Check overall tracking
            assert mock_uuid.uuid4.call_count == 3
            assert len(mock_uuid.uuid4.generated_uuids) == 3

            # Check mocked vs real
            assert mock_uuid.uuid4.mocked_count == 2
            assert mock_uuid.uuid4.real_count == 1

            # Check mocked_calls
            mocked_calls = mock_uuid.uuid4.mocked_calls
            assert len(mocked_calls) == 2
            for call in mocked_calls:
                assert call.was_mocked is True
                assert str(call.uuid) == "12345678-1234-4678-8234-567812345678"

            # Check real_calls
            real_calls = mock_uuid.uuid4.real_calls
            assert len(real_calls) == 1
            assert real_calls[0].was_mocked is False
            assert str(real_calls[0].uuid) != "12345678-1234-4678-8234-567812345678"
        """
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
