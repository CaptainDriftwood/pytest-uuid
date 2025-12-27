"""Tests for the freeze_uuid API."""

from __future__ import annotations

import random
import uuid

import pytest

from pytest_uuid.api import UUIDFreezer, freeze_uuid
from pytest_uuid.config import reset_config
from pytest_uuid.generators import UUIDsExhaustedError


@pytest.fixture(autouse=True)
def reset_config_after_test():
    """Reset config after each test."""
    yield
    reset_config()


class TestFreezeUUIDContextManager:
    """Tests for using freeze_uuid as a context manager."""

    def test_static_uuid(self):
        """Test freezing with a static UUID."""
        with freeze_uuid("12345678-1234-5678-1234-567812345678"):
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-5678-1234-567812345678"

    def test_uuid_sequence(self):
        """Test freezing with a sequence of UUIDs."""
        uuids = [
            "11111111-1111-1111-1111-111111111111",
            "22222222-2222-2222-2222-222222222222",
            "33333333-3333-3333-3333-333333333333",
        ]
        with freeze_uuid(uuids):
            assert str(uuid.uuid4()) == uuids[0]
            assert str(uuid.uuid4()) == uuids[1]
            assert str(uuid.uuid4()) == uuids[2]
            # Cycles by default
            assert str(uuid.uuid4()) == uuids[0]

    def test_sequence_with_raise_on_exhausted(self):
        """Test sequence that raises when exhausted."""
        uuids = ["11111111-1111-1111-1111-111111111111"]
        with freeze_uuid(uuids, on_exhausted="raise"):
            uuid.uuid4()  # First call works
            with pytest.raises(UUIDsExhaustedError):
                uuid.uuid4()

    def test_sequence_with_random_on_exhausted(self):
        """Test sequence that falls back to random."""
        uuids = ["11111111-1111-1111-1111-111111111111"]
        with freeze_uuid(uuids, on_exhausted="random"):
            first = uuid.uuid4()
            assert str(first) == uuids[0]

            # Subsequent calls return random UUIDs
            random_uuid = uuid.uuid4()
            assert str(random_uuid) != uuids[0]
            assert isinstance(random_uuid, uuid.UUID)

    def test_seeded_generation(self):
        """Test seeded UUID generation."""
        with freeze_uuid(seed=42):
            uuid1 = uuid.uuid4()

        with freeze_uuid(seed=42):
            uuid2 = uuid.uuid4()

        assert uuid1 == uuid2

    def test_seeded_with_random_instance(self):
        """Test seeded generation with Random instance."""
        rng = random.Random(42)
        with freeze_uuid(seed=rng):
            result = uuid.uuid4()
            assert isinstance(result, uuid.UUID)
            assert result.version == 4

    def test_reset_in_context(self):
        """Test resetting the generator within context."""
        with freeze_uuid(seed=42) as freezer:
            first = uuid.uuid4()
            uuid.uuid4()  # Skip one
            freezer.reset()
            assert uuid.uuid4() == first

    def test_restores_uuid4_after_exit(self):
        """Test that uuid.uuid4 is restored after exiting context."""
        original = uuid.uuid4

        with freeze_uuid("12345678-1234-5678-1234-567812345678"):
            assert uuid.uuid4 is not original

        assert uuid.uuid4 is original

    def test_uuid_object_input(self):
        """Test using UUID objects as input."""
        expected = uuid.UUID("12345678-1234-5678-1234-567812345678")
        with freeze_uuid(expected):
            assert uuid.uuid4() == expected


class TestFreezeUUIDDecorator:
    """Tests for using freeze_uuid as a decorator."""

    def test_static_uuid_decorator(self):
        """Test decorator with static UUID."""

        @freeze_uuid("12345678-1234-5678-1234-567812345678")
        def my_function():
            return uuid.uuid4()

        result = my_function()
        assert str(result) == "12345678-1234-5678-1234-567812345678"

    def test_seeded_decorator(self):
        """Test decorator with seed."""

        @freeze_uuid(seed=42)
        def my_function():
            return uuid.uuid4()

        result1 = my_function()
        result2 = my_function()

        # Same seed, same result
        assert result1 == result2

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @freeze_uuid("12345678-1234-5678-1234-567812345678")
        def my_function():
            """My docstring."""

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

    def test_class_decorator_static_uuid(self):
        """Test decorator on a class with static UUID."""

        @freeze_uuid("12345678-1234-5678-1234-567812345678")
        class MyTestClass:
            def test_one(self):
                return uuid.uuid4()

            def test_two(self):
                return uuid.uuid4()

        instance = MyTestClass()
        assert str(instance.test_one()) == "12345678-1234-5678-1234-567812345678"
        assert str(instance.test_two()) == "12345678-1234-5678-1234-567812345678"

    def test_class_decorator_seeded(self):
        """Test decorator on a class with seeded generation."""

        @freeze_uuid(seed=42)
        class MyTestClass:
            def test_one(self):
                return uuid.uuid4()

            def test_two(self):
                return uuid.uuid4()

        instance = MyTestClass()
        # Each method gets a fresh seeded generator, so same seed = same first UUID
        result1 = instance.test_one()
        result2 = instance.test_two()
        assert result1 == result2  # Both start from same seed

    def test_class_decorator_method_isolation(self):
        """Test that each method call gets a fresh freeze context."""

        @freeze_uuid(
            [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ]
        )
        class MyTestClass:
            def test_method(self):
                first = uuid.uuid4()
                second = uuid.uuid4()
                return first, second

        instance = MyTestClass()
        first1, second1 = instance.test_method()
        first2, second2 = instance.test_method()

        # Each call starts fresh
        assert str(first1) == "11111111-1111-1111-1111-111111111111"
        assert str(second1) == "22222222-2222-2222-2222-222222222222"
        assert str(first2) == "11111111-1111-1111-1111-111111111111"
        assert str(second2) == "22222222-2222-2222-2222-222222222222"

    def test_class_decorator_only_wraps_test_methods(self):
        """Test that only methods starting with 'test' are wrapped."""

        @freeze_uuid("12345678-1234-5678-1234-567812345678")
        class MyTestClass:
            def test_method(self):
                return uuid.uuid4()

            def helper_method(self):
                return uuid.uuid4()

        instance = MyTestClass()

        # test_method is wrapped
        assert str(instance.test_method()) == "12345678-1234-5678-1234-567812345678"

        # helper_method is NOT wrapped - returns real random UUID
        helper_result = instance.helper_method()
        assert str(helper_result) != "12345678-1234-5678-1234-567812345678"

    def test_class_decorator_preserves_class_identity(self):
        """Test that the decorated class is still the same class."""

        @freeze_uuid("12345678-1234-5678-1234-567812345678")
        class MyTestClass:
            class_attr = "value"

            def test_method(self):
                return uuid.uuid4()

        assert MyTestClass.class_attr == "value"
        assert MyTestClass.__name__ == "MyTestClass"


class TestUUIDFreezer:
    """Tests for the UUIDFreezer class directly."""

    def test_node_seed_requires_node_id(self):
        """Test that seed='node' requires node_id."""
        freezer = UUIDFreezer(seed="node")
        with pytest.raises(ValueError, match="node_id"):
            freezer.__enter__()

    def test_node_seed_with_node_id(self):
        """Test node-seeded generation with node_id."""
        with UUIDFreezer(seed="node", node_id="test.py::test_foo"):
            uuid1 = uuid.uuid4()

        with UUIDFreezer(seed="node", node_id="test.py::test_foo"):
            uuid2 = uuid.uuid4()

        # Same node ID, same UUID
        assert uuid1 == uuid2

    def test_different_node_ids_produce_different_uuids(self):
        """Test that different node IDs produce different UUIDs."""
        with UUIDFreezer(seed="node", node_id="test.py::test_foo"):
            uuid1 = uuid.uuid4()

        with UUIDFreezer(seed="node", node_id="test.py::test_bar"):
            uuid2 = uuid.uuid4()

        assert uuid1 != uuid2

    def test_generator_property(self):
        """Test the generator property."""
        freezer = UUIDFreezer("12345678-1234-5678-1234-567812345678")

        assert freezer.generator is None

        with freezer:
            assert freezer.generator is not None

        assert freezer.generator is None


class TestUUIDFreezerCallTracking:
    """Integration tests for UUIDFreezer call tracking.

    Note: The CallTrackingMixin is thoroughly tested in test_tracking.py.
    These tests verify that freeze_uuid properly integrates call tracking.
    """

    def test_freezer_integrates_call_tracking(self):
        """Test that freeze_uuid properly integrates CallTrackingMixin."""
        with freeze_uuid(
            [
                "11111111-1111-1111-1111-111111111111",
                "22222222-2222-2222-2222-222222222222",
            ]
        ) as freezer:
            result1 = uuid.uuid4()
            result2 = uuid.uuid4()

            assert freezer.call_count == 2
            assert freezer.generated_uuids == [result1, result2]
            assert freezer.last_uuid == result2
            assert freezer.mocked_count == 2
            assert all(c.was_mocked for c in freezer.calls)

    def test_reset_clears_tracking_and_restarts_sequence(self):
        """Test that reset clears tracking and restarts the UUID sequence."""
        with freeze_uuid(seed=42) as freezer:
            first = uuid.uuid4()
            uuid.uuid4()

            freezer.reset()

            assert freezer.call_count == 0
            assert freezer.last_uuid is None
            # After reset, sequence restarts
            assert uuid.uuid4() == first


class TestFreezeUUIDWithDirectImport:
    """Tests for freeze_uuid with 'from uuid import uuid4' pattern."""

    def test_patches_direct_imports(self):
        """Test that direct imports are also patched."""
        from uuid import uuid4 as _  # noqa: F401

        with freeze_uuid("12345678-1234-5678-1234-567812345678"):
            # This tests that the patching handles direct imports
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-5678-1234-567812345678"

    def test_restores_direct_imports(self):
        """Test that direct imports are restored after exit."""
        from uuid import uuid4 as local_uuid4

        original = local_uuid4

        with freeze_uuid("12345678-1234-5678-1234-567812345678"):
            pass

        # After exiting, uuid.uuid4 should be restored
        # Note: local_uuid4 keeps its original reference
        assert uuid.uuid4 is original


class TestFreezeUUIDNested:
    """Tests for nested freeze_uuid contexts."""

    def test_nested_contexts(self):
        """Test that nested contexts work correctly."""
        with freeze_uuid("11111111-1111-1111-1111-111111111111"):
            assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"

            with freeze_uuid("22222222-2222-2222-2222-222222222222"):
                assert str(uuid.uuid4()) == "22222222-2222-2222-2222-222222222222"

            # Outer context is restored
            assert str(uuid.uuid4()) == "11111111-1111-1111-1111-111111111111"


class TestThreadSafety:
    """Tests for thread-safe UUID freezing."""

    def test_concurrent_uuid_calls_all_mocked(self):
        """Test that concurrent uuid4 calls all return mocked value."""
        import threading

        expected = "12345678-1234-5678-1234-567812345678"
        results: list[str] = []
        errors: list[Exception] = []

        def call_uuid():
            try:
                results.append(str(uuid.uuid4()))
            except Exception as e:
                errors.append(e)

        with freeze_uuid(expected):
            threads = [threading.Thread(target=call_uuid) for _ in range(50)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert not errors, f"Errors occurred: {errors}"
        assert len(results) == 50
        assert all(r == expected for r in results), (
            f"Not all results matched: {set(results)}"
        )

    def test_concurrent_seeded_generation(self):
        """Test that concurrent seeded generation works correctly."""
        import threading

        results: list[uuid.UUID] = []
        lock = threading.Lock()

        def call_uuid():
            result = uuid.uuid4()
            with lock:
                results.append(result)

        with freeze_uuid(seed=42) as freezer:
            threads = [threading.Thread(target=call_uuid) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All 20 calls should be tracked
            assert freezer.call_count == 20

        # All results should be valid UUIDs
        assert len(results) == 20
        assert all(isinstance(r, uuid.UUID) for r in results)

    def test_call_tracking_thread_safe(self):
        """Test that call tracking works correctly with concurrent calls."""
        import threading

        expected = "12345678-1234-5678-1234-567812345678"

        with freeze_uuid(expected) as freezer:
            threads = [threading.Thread(target=uuid.uuid4) for _ in range(30)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All 30 calls should be tracked
            assert freezer.call_count == 30
            assert len(freezer.generated_uuids) == 30
            assert len(freezer.calls) == 30


class TestLateImports:
    """Tests for importing uuid4 after freeze context starts."""

    def test_late_import_after_freeze_is_patched(self):
        """Test that importing uuid4 after freeze starts still gets mocked."""
        expected = "12345678-1234-5678-1234-567812345678"

        with freeze_uuid(expected):
            # Import uuid4 INSIDE the freeze context - this gets the patched version
            from uuid import uuid4 as late_imported_uuid4

            result = late_imported_uuid4()
            assert str(result) == expected
