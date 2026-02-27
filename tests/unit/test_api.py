"""Tests for the freeze_uuid API."""

from __future__ import annotations

import random
import threading
import uuid

import pytest

from pytest_uuid.api import (
    UUIDFreezer,
    freeze_uuid,
    freeze_uuid1,
    freeze_uuid4,
    freeze_uuid6,
    freeze_uuid7,
    freeze_uuid8,
)
from pytest_uuid.generators import UUIDsExhaustedError

# --- freeze_uuid as context manager ---


def test_freeze_context_static_uuid():
    """Test freezing with a static UUID."""
    with freeze_uuid("12345678-1234-4678-8234-567812345678"):
        result = uuid.uuid4()
        assert str(result) == "12345678-1234-4678-8234-567812345678"


def test_freeze_context_uuid_sequence():
    """Test freezing with a sequence of UUIDs."""
    uuids = [
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
    ]
    with freeze_uuid(uuids):
        assert str(uuid.uuid4()) == uuids[0]
        assert str(uuid.uuid4()) == uuids[1]
        assert str(uuid.uuid4()) == uuids[2]
        # Cycles by default
        assert str(uuid.uuid4()) == uuids[0]


def test_freeze_context_sequence_raise_on_exhausted():
    """Test sequence that raises when exhausted."""
    uuids = ["11111111-1111-4111-8111-111111111111"]
    with freeze_uuid(uuids, on_exhausted="raise"):
        uuid.uuid4()  # First call works
        with pytest.raises(UUIDsExhaustedError):
            uuid.uuid4()


def test_freeze_context_sequence_random_on_exhausted():
    """Test sequence that falls back to random."""
    uuids = ["11111111-1111-4111-8111-111111111111"]
    with freeze_uuid(uuids, on_exhausted="random"):
        first = uuid.uuid4()
        assert str(first) == uuids[0]

        # Subsequent calls return random UUIDs
        random_uuid = uuid.uuid4()
        assert str(random_uuid) != uuids[0]
        assert isinstance(random_uuid, uuid.UUID)


def test_freeze_context_seeded_generation():
    """Test seeded UUID generation."""
    with freeze_uuid(seed=42):
        uuid1 = uuid.uuid4()

    with freeze_uuid(seed=42):
        uuid2 = uuid.uuid4()

    assert uuid1 == uuid2


def test_freeze_context_seeded_with_random_instance():
    """Test seeded generation with Random instance."""
    rng = random.Random(42)
    with freeze_uuid(seed=rng):
        result = uuid.uuid4()
        assert isinstance(result, uuid.UUID)
        assert result.version == 4


def test_freeze_context_reset():
    """Test resetting the generator within context."""
    with freeze_uuid(seed=42) as freezer:
        first = uuid.uuid4()
        uuid.uuid4()  # Skip one
        freezer.reset()
        assert uuid.uuid4() == first


def test_freeze_context_restores_behavior_after_exit():
    """Test that uuid.uuid4 generates random UUIDs after exiting context."""
    # With the proxy approach, uuid.uuid4 is always the proxy
    # But behavior changes based on context variable
    with freeze_uuid("12345678-1234-4678-8234-567812345678"):
        mocked = uuid.uuid4()
        assert str(mocked) == "12345678-1234-4678-8234-567812345678"

    # After exit, should return random UUIDs (not the mocked one)
    random1 = uuid.uuid4()
    random2 = uuid.uuid4()
    # Random UUIDs should be different from each other and from the mocked one
    assert random1 != random2
    assert str(random1) != "12345678-1234-4678-8234-567812345678"


def test_freeze_context_uuid_object_input():
    """Test using UUID objects as input."""
    expected = uuid.UUID("12345678-1234-4678-8234-567812345678")
    with freeze_uuid(expected):
        assert uuid.uuid4() == expected


# --- freeze_uuid as decorator ---


def test_freeze_decorator_static_uuid():
    """Test decorator with static UUID."""

    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    def my_function():
        return uuid.uuid4()

    result = my_function()
    assert str(result) == "12345678-1234-4678-8234-567812345678"


def test_freeze_decorator_seeded():
    """Test decorator with seed."""

    @freeze_uuid(seed=42)
    def my_function():
        return uuid.uuid4()

    result1 = my_function()
    result2 = my_function()

    # Same seed, same result
    assert result1 == result2


def test_freeze_decorator_preserves_function_metadata():
    """Test that decorator preserves function name and docstring."""

    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    def my_function():
        """My docstring."""

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


def test_freeze_decorator_class_static_uuid():
    """Test decorator on a class with static UUID."""

    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    class MyTestClass:
        def test_one(self):
            return uuid.uuid4()

        def test_two(self):
            return uuid.uuid4()

    instance = MyTestClass()
    assert str(instance.test_one()) == "12345678-1234-4678-8234-567812345678"
    assert str(instance.test_two()) == "12345678-1234-4678-8234-567812345678"


def test_freeze_decorator_class_seeded():
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


def test_freeze_decorator_class_method_isolation():
    """Test that each method call gets a fresh freeze context."""

    @freeze_uuid(
        [
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
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
    assert str(first1) == "11111111-1111-4111-8111-111111111111"
    assert str(second1) == "22222222-2222-4222-8222-222222222222"
    assert str(first2) == "11111111-1111-4111-8111-111111111111"
    assert str(second2) == "22222222-2222-4222-8222-222222222222"


def test_freeze_decorator_class_only_wraps_test_methods():
    """Test that only methods starting with 'test' are wrapped."""

    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    class MyTestClass:
        def test_method(self):
            return uuid.uuid4()

        def helper_method(self):
            return uuid.uuid4()

    instance = MyTestClass()

    # test_method is wrapped
    assert str(instance.test_method()) == "12345678-1234-4678-8234-567812345678"

    # helper_method is NOT wrapped - returns real random UUID
    helper_result = instance.helper_method()
    assert str(helper_result) != "12345678-1234-4678-8234-567812345678"


def test_freeze_decorator_class_preserves_class_identity():
    """Test that the decorated class is still the same class."""

    @freeze_uuid("12345678-1234-4678-8234-567812345678")
    class MyTestClass:
        class_attr = "value"

        def test_method(self):
            return uuid.uuid4()

    assert MyTestClass.class_attr == "value"
    assert MyTestClass.__name__ == "MyTestClass"


# --- UUIDFreezer class ---


def test_freezer_node_seed_requires_node_id():
    """Test that seed='node' requires node_id."""
    freezer = UUIDFreezer(seed="node")
    with pytest.raises(ValueError, match="node_id"):
        freezer.__enter__()


def test_freezer_node_seed_with_node_id():
    """Test node-seeded generation with node_id."""
    with UUIDFreezer(seed="node", node_id="test.py::test_foo"):
        uuid1 = uuid.uuid4()

    with UUIDFreezer(seed="node", node_id="test.py::test_foo"):
        uuid2 = uuid.uuid4()

    # Same node ID, same UUID
    assert uuid1 == uuid2


def test_freezer_different_node_ids_produce_different_uuids():
    """Test that different node IDs produce different UUIDs."""
    with UUIDFreezer(seed="node", node_id="test.py::test_foo"):
        uuid1 = uuid.uuid4()

    with UUIDFreezer(seed="node", node_id="test.py::test_bar"):
        uuid2 = uuid.uuid4()

    assert uuid1 != uuid2


def test_freezer_generator_property():
    """Test the generator property."""
    freezer = UUIDFreezer("12345678-1234-4678-8234-567812345678")

    assert freezer.generator is None

    with freezer:
        assert freezer.generator is not None

    assert freezer.generator is None


def test_freezer_seed_property_with_integer():
    """Test that seed property returns the integer seed."""
    with UUIDFreezer(seed=42) as freezer:
        assert freezer.seed == 42


def test_freezer_seed_property_with_node_seed():
    """Test that seed property returns computed seed when using seed='node'."""
    with UUIDFreezer(seed="node", node_id="test.py::test_foo") as freezer:
        # Should return an integer, not "node"
        assert freezer.seed is not None
        assert isinstance(freezer.seed, int)


def test_freezer_seed_property_with_random_instance():
    """Test that seed property returns None when using Random instance."""
    rng = random.Random(42)
    with UUIDFreezer(seed=rng) as freezer:
        assert freezer.seed is None


def test_freezer_seed_property_with_static_uuid():
    """Test that seed property returns None when using static UUIDs."""
    with UUIDFreezer("12345678-1234-4678-8234-567812345678") as freezer:
        assert freezer.seed is None


def test_freezer_seed_property_when_not_active():
    """Test that seed property returns None when freezer is not active."""
    freezer = UUIDFreezer(seed=42)
    assert freezer.seed is None


# --- UUIDFreezer call tracking integration ---


def test_freezer_integrates_call_tracking():
    """Test that freeze_uuid properly integrates CallTrackingMixin."""
    with freeze_uuid(
        [
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ]
    ) as freezer:
        result1 = uuid.uuid4()
        result2 = uuid.uuid4()

        assert freezer.call_count == 2
        assert freezer.generated_uuids == [result1, result2]
        assert freezer.last_uuid == result2
        assert freezer.mocked_count == 2
        assert all(c.was_mocked for c in freezer.calls)


def test_freezer_reset_clears_tracking_and_restarts_sequence():
    """Test that reset clears tracking and restarts the UUID sequence."""
    with freeze_uuid(seed=42) as freezer:
        first = uuid.uuid4()
        uuid.uuid4()

        freezer.reset()

        assert freezer.call_count == 0
        assert freezer.last_uuid is None
        # After reset, sequence restarts
        assert uuid.uuid4() == first


# --- freeze_uuid with direct imports ---


def test_freeze_patches_direct_imports():
    """Test that direct imports are also patched."""
    from uuid import uuid4 as _  # noqa: F401

    with freeze_uuid("12345678-1234-4678-8234-567812345678"):
        # This tests that the patching handles direct imports
        result = uuid.uuid4()
        assert str(result) == "12345678-1234-4678-8234-567812345678"


def test_freeze_restores_direct_imports():
    """Test that direct imports are restored after exit."""
    from uuid import uuid4 as local_uuid4

    original = local_uuid4

    with freeze_uuid("12345678-1234-4678-8234-567812345678"):
        pass

    # After exiting, uuid.uuid4 should be restored
    # Note: local_uuid4 keeps its original reference
    assert uuid.uuid4 is original


# --- Nested freeze_uuid contexts ---


def test_freeze_nested_contexts():
    """Test that nested contexts work correctly."""
    with freeze_uuid("11111111-1111-4111-8111-111111111111"):
        assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"

        with freeze_uuid("22222222-2222-4222-8222-222222222222"):
            assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"

        # Outer context is restored
        assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"


# --- Thread safety ---


def test_freeze_concurrent_uuid_calls_all_mocked():
    """Test that concurrent uuid4 calls all return mocked value."""
    expected = "12345678-1234-4678-8234-567812345678"
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


def test_freeze_concurrent_seeded_generation():
    """Test that concurrent seeded generation works correctly."""
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


def test_freeze_call_tracking_thread_safe():
    """Test that call tracking works correctly with concurrent calls."""
    expected = "12345678-1234-4678-8234-567812345678"

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


# --- Late imports ---


def test_freeze_late_import_is_patched():
    """Test that importing uuid4 after freeze starts still gets mocked."""
    expected = "12345678-1234-4678-8234-567812345678"

    with freeze_uuid(expected):
        # Import uuid4 INSIDE the freeze context - this gets the patched version
        from uuid import uuid4 as late_imported_uuid4

        result = late_imported_uuid4()
        assert str(result) == expected


# --- ignore_defaults parameter tests ---


def test_ignore_defaults_true_includes_default_packages():
    """With ignore_defaults=True (default), DEFAULT_IGNORE_PACKAGES are ignored."""
    with freeze_uuid("11111111-1111-4111-8111-111111111111") as freezer:
        # Verify botocore is in the ignore list
        assert "botocore" in freezer._ignore_list
        # Direct call should be mocked
        result = uuid.uuid4()
        assert str(result) == "11111111-1111-4111-8111-111111111111"


def test_ignore_defaults_false_excludes_default_packages():
    """With ignore_defaults=False, DEFAULT_IGNORE_PACKAGES are NOT ignored."""
    with freeze_uuid(
        "22222222-2222-4222-8222-222222222222", ignore_defaults=False
    ) as freezer:
        # Verify botocore is NOT in the ignore list
        assert "botocore" not in freezer._ignore_list
        # Direct call should still be mocked
        result = uuid.uuid4()
        assert str(result) == "22222222-2222-4222-8222-222222222222"


def test_ignore_defaults_false_with_custom_ignore():
    """ignore_defaults=False + ignore=['foo'] only ignores 'foo'."""
    with freeze_uuid(
        "33333333-3333-4333-8333-333333333333",
        ignore=["mymodule"],
        ignore_defaults=False,
    ) as freezer:
        # Only mymodule should be in ignore list, not botocore
        assert "mymodule" in freezer._ignore_list
        assert "botocore" not in freezer._ignore_list


def test_ignore_defaults_true_with_custom_ignore_combines():
    """ignore_defaults=True + ignore=['foo'] ignores both defaults and 'foo'."""
    with freeze_uuid(
        "44444444-4444-4444-9444-444444444444",
        ignore=["mymodule"],
        ignore_defaults=True,  # This is the default
    ) as freezer:
        # Both mymodule and botocore should be in ignore list
        assert "mymodule" in freezer._ignore_list
        assert "botocore" in freezer._ignore_list


def test_decorator_respects_ignore_defaults_false():
    """@freeze_uuid decorator also respects ignore_defaults."""

    @freeze_uuid("55555555-5555-4555-9555-555555555555", ignore_defaults=False)
    def func():
        return uuid.uuid4()

    result = func()
    assert str(result) == "55555555-5555-4555-9555-555555555555"


# --- Ignore list tracking tests ---


def test_ignored_calls_tracked_with_was_mocked_false():
    """Verify that ignored module calls ARE tracked with was_mocked=False.

    When a module in the ignore list calls uuid.uuid4(), the call should:
    - Return a real UUID (not from the seeded sequence)
    - BE tracked (call_count increments, added to calls list)
    - Be marked with was_mocked=False

    This allows debugging visibility while still returning real UUIDs.
    """
    with freeze_uuid(seed=42, ignore=["tests"]) as freezer:
        # Make a call that will be detected as "from ignored module"
        # (the tests module is in the ignore list)
        result = uuid.uuid4()

        # The call IS tracked (for debugging visibility)
        assert freezer.call_count == 1, "Ignored calls should be tracked"
        assert len(freezer.calls) == 1, "Ignored calls should appear in calls list"
        assert len(freezer.generated_uuids) == 1

        # But marked as not mocked
        call = freezer.calls[0]
        assert call.was_mocked is False, "Ignored calls should have was_mocked=False"
        assert len(freezer.real_calls) == 1
        assert len(freezer.mocked_calls) == 0

        # The result should be a real v4 UUID (not from our seeded generator)
        assert result.version == 4
        assert freezer.generated_uuids[0] == result


# =============================================================================
# Version-specific freeze functions
# =============================================================================


class TestFreezeUUID4:
    """Tests for freeze_uuid4 function."""

    def test_static_uuid(self):
        """Test freeze_uuid4 with a static UUID."""
        with freeze_uuid4("12345678-1234-4678-8234-567812345678"):
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"

    def test_seeded_generation(self):
        """Test freeze_uuid4 with seeded generation."""
        with freeze_uuid4(seed=42):
            uuid1 = uuid.uuid4()

        with freeze_uuid4(seed=42):
            uuid2 = uuid.uuid4()

        assert uuid1 == uuid2
        assert uuid1.version == 4

    def test_as_decorator(self):
        """Test freeze_uuid4 as a decorator."""

        @freeze_uuid4("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
        def get_uuid():
            return uuid.uuid4()

        result = get_uuid()
        assert str(result) == "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

    def test_uuid_version_property(self):
        """Test that uuid_version property returns correct version."""
        with freeze_uuid4(seed=42) as freezer:
            assert freezer.uuid_version == "uuid4"


class TestFreezeUUID1:
    """Tests for freeze_uuid1 function."""

    def test_static_uuid(self):
        """Test freeze_uuid1 with a static UUID."""
        with freeze_uuid1("12345678-1234-1678-8234-567812345678"):
            result = uuid.uuid1()
            assert str(result) == "12345678-1234-1678-8234-567812345678"

    def test_seeded_generation(self):
        """Test freeze_uuid1 with seeded generation."""
        with freeze_uuid1(seed=42):
            uuid1 = uuid.uuid1()

        with freeze_uuid1(seed=42):
            uuid2 = uuid.uuid1()

        assert uuid1 == uuid2
        assert uuid1.version == 1

    def test_seeded_with_fixed_node(self):
        """Test freeze_uuid1 with seeded generation and fixed node."""
        fixed_node = 0x123456789ABC

        with freeze_uuid1(seed=42, node=fixed_node):
            result = uuid.uuid1()
            assert result.node == fixed_node
            assert result.version == 1

    def test_seeded_with_fixed_clock_seq(self):
        """Test freeze_uuid1 with seeded generation and fixed clock_seq."""
        fixed_clock_seq = 0x1234

        with freeze_uuid1(seed=42, clock_seq=fixed_clock_seq):
            result = uuid.uuid1()
            assert result.clock_seq == fixed_clock_seq
            assert result.version == 1

    def test_seeded_with_node_and_clock_seq(self):
        """Test freeze_uuid1 with both node and clock_seq."""
        fixed_node = 0x123456789ABC
        fixed_clock_seq = 0x1234

        with freeze_uuid1(seed=42, node=fixed_node, clock_seq=fixed_clock_seq):
            result = uuid.uuid1()
            assert result.node == fixed_node
            assert result.clock_seq == fixed_clock_seq
            assert result.version == 1

    def test_sequence(self):
        """Test freeze_uuid1 with multiple UUIDs."""
        uuids = [
            "11111111-1111-1111-8111-111111111111",
            "22222222-2222-1222-8222-222222222222",
        ]
        with freeze_uuid1(uuids):
            assert str(uuid.uuid1()) == uuids[0]
            assert str(uuid.uuid1()) == uuids[1]

    def test_uuid_version_property(self):
        """Test that uuid_version property returns correct version."""
        with freeze_uuid1(seed=42) as freezer:
            assert freezer.uuid_version == "uuid1"


class TestFreezeUUID6:
    """Tests for freeze_uuid6 function."""

    def test_static_uuid(self):
        """Test freeze_uuid6 with a static UUID."""
        uuid6_mod = pytest.importorskip("uuid6")

        with freeze_uuid6("12345678-1234-6678-8234-567812345678"):
            result = uuid6_mod.uuid6()
            assert str(result) == "12345678-1234-6678-8234-567812345678"

    def test_seeded_generation(self):
        """Test freeze_uuid6 with seeded generation."""
        uuid6_mod = pytest.importorskip("uuid6")

        with freeze_uuid6(seed=42):
            uuid1 = uuid6_mod.uuid6()

        with freeze_uuid6(seed=42):
            uuid2 = uuid6_mod.uuid6()

        assert uuid1 == uuid2
        assert uuid1.version == 6

    def test_seeded_with_fixed_node(self):
        """Test freeze_uuid6 with seeded generation and fixed node."""
        uuid6_mod = pytest.importorskip("uuid6")
        fixed_node = 0x123456789ABC

        with freeze_uuid6(seed=42, node=fixed_node):
            result = uuid6_mod.uuid6()
            assert result.node == fixed_node
            assert result.version == 6

    def test_seeded_with_fixed_clock_seq(self):
        """Test freeze_uuid6 with seeded generation and fixed clock_seq."""
        uuid6_mod = pytest.importorskip("uuid6")
        fixed_clock_seq = 0x1234

        with freeze_uuid6(seed=42, clock_seq=fixed_clock_seq):
            result = uuid6_mod.uuid6()
            assert result.clock_seq == fixed_clock_seq
            assert result.version == 6

    def test_sequence(self):
        """Test freeze_uuid6 with multiple UUIDs."""
        uuid6_mod = pytest.importorskip("uuid6")
        uuids = [
            "12345678-1234-6678-8234-567812345678",
            "87654321-4321-6876-8432-876543218765",
        ]
        with freeze_uuid6(uuids):
            assert str(uuid6_mod.uuid6()) == uuids[0]
            assert str(uuid6_mod.uuid6()) == uuids[1]

    def test_uuid_version_property(self):
        """Test that uuid_version property returns correct version."""
        pytest.importorskip("uuid6")
        with freeze_uuid6(seed=42) as freezer:
            assert freezer.uuid_version == "uuid6"


class TestFreezeUUID7:
    """Tests for freeze_uuid7 function."""

    def test_static_uuid(self):
        """Test freeze_uuid7 with a static UUID."""
        # Use uuid7 (requires uuid6 package or Python 3.14+)
        uuid6_mod = pytest.importorskip("uuid6")

        # Import uuid7 from the patched uuid6 module (NOT from _compat)
        with freeze_uuid7("01234567-89ab-7def-8123-456789abcdef"):
            result = uuid6_mod.uuid7()
            assert str(result) == "01234567-89ab-7def-8123-456789abcdef"

    def test_seeded_generation(self):
        """Test freeze_uuid7 with seeded generation."""
        uuid6_mod = pytest.importorskip("uuid6")

        with freeze_uuid7(seed=42):
            uuid1 = uuid6_mod.uuid7()

        with freeze_uuid7(seed=42):
            uuid2 = uuid6_mod.uuid7()

        assert uuid1 == uuid2
        assert uuid1.version == 7

    def test_sequence(self):
        """Test freeze_uuid7 with multiple UUIDs."""
        uuid6_mod = pytest.importorskip("uuid6")
        uuids = [
            "01234567-89ab-7def-8123-456789abcdef",
            "fedcba98-7654-7321-8fed-cba987654321",
        ]
        with freeze_uuid7(uuids):
            assert str(uuid6_mod.uuid7()) == uuids[0]
            assert str(uuid6_mod.uuid7()) == uuids[1]


class TestFreezeUUID8:
    """Tests for freeze_uuid8 function."""

    def test_static_uuid(self):
        """Test freeze_uuid8 with a static UUID."""
        uuid6_mod = pytest.importorskip("uuid6")

        with freeze_uuid8("12345678-1234-8678-8234-567812345678"):
            result = uuid6_mod.uuid8()
            assert str(result) == "12345678-1234-8678-8234-567812345678"

    def test_seeded_generation(self):
        """Test freeze_uuid8 with seeded generation."""
        uuid6_mod = pytest.importorskip("uuid6")

        with freeze_uuid8(seed=42):
            uuid1 = uuid6_mod.uuid8()

        with freeze_uuid8(seed=42):
            uuid2 = uuid6_mod.uuid8()

        assert uuid1 == uuid2
        assert uuid1.version == 8

    def test_sequence(self):
        """Test freeze_uuid8 with multiple UUIDs."""
        uuid6_mod = pytest.importorskip("uuid6")
        uuids = [
            "12345678-1234-8678-8234-567812345678",
            "87654321-4321-8876-8432-876543218765",
        ]
        with freeze_uuid8(uuids):
            assert str(uuid6_mod.uuid8()) == uuids[0]
            assert str(uuid6_mod.uuid8()) == uuids[1]


class TestStackingMultipleVersionFreezers:
    """Tests for stacking multiple version freezers."""

    def test_stack_uuid4_and_uuid1(self):
        """Test stacking freeze_uuid4 and freeze_uuid1."""
        with (
            freeze_uuid4("aaaa4444-aaaa-4aaa-aaaa-aaaaaaaaaaaa"),
            freeze_uuid1("bbbb1111-bbbb-1bbb-bbbb-bbbbbbbbbbbb"),
        ):
            # uuid4 should return the frozen uuid4 value
            result4 = uuid.uuid4()
            assert str(result4) == "aaaa4444-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

            # uuid1 should return the frozen uuid1 value
            result1 = uuid.uuid1()
            assert str(result1) == "bbbb1111-bbbb-1bbb-bbbb-bbbbbbbbbbbb"

    def test_stack_seeded_generators(self):
        """Test stacking multiple seeded generators."""
        with (
            freeze_uuid4(seed=42) as f4,
            freeze_uuid1(seed=43) as f1,
        ):
            uuid4_result = uuid.uuid4()
            uuid1_result = uuid.uuid1()

            assert uuid4_result.version == 4
            assert uuid1_result.version == 1
            assert f4.call_count == 1
            assert f1.call_count == 1

    def test_stack_uuid7_and_uuid4(self):
        """Test stacking freeze_uuid7 and freeze_uuid4."""
        uuid6_mod = pytest.importorskip("uuid6")

        with (
            freeze_uuid4("44444444-4444-4444-8444-444444444444"),
            freeze_uuid7(seed=42),
        ):
            result4 = uuid.uuid4()
            result7 = uuid6_mod.uuid7()

            assert result4.version == 4
            assert result7.version == 7


class TestBackwardCompatibility:
    """Tests for backward compatibility of freeze_uuid alias."""

    def test_freeze_uuid_is_alias_for_uuid4(self):
        """Test that freeze_uuid still works and freezes uuid4."""
        # freeze_uuid should be an alias for freeze_uuid4
        with freeze_uuid("12345678-1234-4678-8234-567812345678") as freezer:
            result = uuid.uuid4()
            assert str(result) == "12345678-1234-4678-8234-567812345678"
            assert freezer.uuid_version == "uuid4"

    def test_freeze_uuid_seeded(self):
        """Test freeze_uuid with seeded generation."""
        with freeze_uuid(seed=42):
            uuid1 = uuid.uuid4()

        with freeze_uuid(seed=42):
            uuid2 = uuid.uuid4()

        assert uuid1 == uuid2


class TestVersionSpecificDecorators:
    """Tests for using version-specific freezers as decorators."""

    def test_freeze_uuid1_as_decorator(self):
        """Test freeze_uuid1 as a function decorator."""

        @freeze_uuid1("11111111-1111-1111-8111-111111111111")
        def func():
            return uuid.uuid1()

        result = func()
        assert str(result) == "11111111-1111-1111-8111-111111111111"

    def test_freeze_uuid1_decorator_with_node(self):
        """Test freeze_uuid1 decorator with node parameter."""
        fixed_node = 0x123456789ABC

        @freeze_uuid1(seed=42, node=fixed_node)
        def func():
            return uuid.uuid1()

        result = func()
        assert result.node == fixed_node
        assert result.version == 1

    def test_freeze_uuid6_as_decorator(self):
        """Test freeze_uuid6 as a function decorator."""
        uuid6_mod = pytest.importorskip("uuid6")

        @freeze_uuid6("12345678-1234-6678-8234-567812345678")
        def func():
            return uuid6_mod.uuid6()

        result = func()
        assert str(result) == "12345678-1234-6678-8234-567812345678"

    def test_freeze_uuid7_as_decorator(self):
        """Test freeze_uuid7 as a function decorator."""
        uuid6_mod = pytest.importorskip("uuid6")

        @freeze_uuid7("01234567-89ab-7def-8123-456789abcdef")
        def func():
            return uuid6_mod.uuid7()

        result = func()
        assert str(result) == "01234567-89ab-7def-8123-456789abcdef"

    def test_freeze_uuid8_as_decorator(self):
        """Test freeze_uuid8 as a function decorator."""
        uuid6_mod = pytest.importorskip("uuid6")

        @freeze_uuid8("12345678-1234-8678-8234-567812345678")
        def func():
            return uuid6_mod.uuid8()

        result = func()
        assert str(result) == "12345678-1234-8678-8234-567812345678"

    def test_freeze_uuid1_as_class_decorator(self):
        """Test freeze_uuid1 as a class decorator."""

        @freeze_uuid1(seed=42)
        class TestClass:
            def method(self):
                return uuid.uuid1()

        obj = TestClass()
        result = obj.method()
        assert result.version == 1

    def test_stacked_decorators(self):
        """Test stacking multiple version-specific decorators."""

        @freeze_uuid4("44444444-4444-4444-8444-444444444444")
        @freeze_uuid1("11111111-1111-1111-8111-111111111111")
        def func():
            return uuid.uuid4(), uuid.uuid1()

        result4, result1 = func()
        assert str(result4) == "44444444-4444-4444-8444-444444444444"
        assert str(result1) == "11111111-1111-1111-8111-111111111111"
