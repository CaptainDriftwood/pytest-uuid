"""Tests for botocore ignore list behavior with freeze_uuid.

These tests verify that botocore's uuid.uuid4() calls (triggered by S3 operations)
are properly ignored and don't affect the seeded UUID sequence.
"""

from __future__ import annotations

import uuid

import boto3
import moto
import pytest

from pytest_uuid import freeze_uuid


@pytest.fixture
def bucket_name():
    """Return the test bucket name."""
    return "test-bucket"


@pytest.fixture(autouse=True)
def mock_aws(bucket_name):
    """Mock AWS services for all tests in this module."""
    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=bucket_name)
        yield


@pytest.fixture
def s3_client():
    """Create an S3 bucket for testing."""
    return boto3.client("s3", region_name="us-east-1")


@pytest.fixture
def upload_file(bucket_name, s3_client):
    """Return a callable that uploads a file to S3 using put_object.

    This triggers botocore.endpoint uuid.uuid4() calls internally.
    """

    def _upload(key: str):
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=b"test content",
        )

    return _upload


@pytest.mark.botocore
def test_ignored_calls_tracked_with_was_mocked_false_botocore(upload_file):
    """Verify that botocore's uuid.uuid4() calls ARE tracked with was_mocked=False.

    When botocore (in the default ignore list) calls uuid.uuid4(), the call should:
    - Return a real UUID (not from the seeded sequence)
    - BE tracked (call_count increments, added to calls list)
    - Be marked with was_mocked=False
    """
    with freeze_uuid(seed=42) as freezer:
        # Upload triggers botocore.endpoint uuid.uuid4()
        upload_file("test.txt")

        # The botocore call should be tracked
        assert freezer.call_count >= 1, "Botocore calls should be tracked"

        # Find the botocore calls
        botocore_calls = [
            c for c in freezer.calls if c.caller_module.startswith("botocore")
        ]
        assert len(botocore_calls) >= 1, "Should have at least one botocore call"

        # Botocore calls should be marked as not mocked
        for call in botocore_calls:
            assert call.was_mocked is False, (
                f"Botocore call should have was_mocked=False, got {call}"
            )


@pytest.mark.botocore
def test_botocore_put_object_does_not_affect_seeded_sequence(upload_file):
    """Test that botocore's uuid.uuid4() calls don't affect the seeded sequence.

    This test reproduces the bug scenario from the downstream project:
    1. Start freeze_uuid with seed and botocore in ignore list (default)
    2. Call put_object() which triggers botocore.endpoint uuid.uuid4()
    3. Call uuid.uuid4() directly from test code
    4. Verify the seeded UUID is at position 0 (not shifted)

    If the bug exists, the seeded sequence will be shifted because botocore's
    uuid.uuid4() call was tracked (even though it returned a real UUID).
    """
    # First, establish baseline: what UUIDs does seed=42 produce?
    with freeze_uuid(seed=42) as freezer_baseline:
        baseline_uuid1 = uuid.uuid4()
        baseline_uuid2 = uuid.uuid4()
        assert freezer_baseline.call_count == 2
        assert freezer_baseline.mocked_count == 2

    # Now the bug scenario: put_object triggers botocore uuid.uuid4()
    with freeze_uuid(seed=42) as freezer:
        # put_object triggers botocore.endpoint uuid.uuid4()
        # botocore is in the default ignore list, so it should get a real UUID
        upload_file("test.txt")
        upload_file("test_1.txt")

        # Check if botocore's call was tracked
        botocore_calls = [
            c for c in freezer.calls if c.caller_module.startswith("botocore")
        ]

        # Now call uuid.uuid4() directly - this should be mocked
        handler_uuid1 = uuid.uuid4()
        handler_uuid2 = uuid.uuid4()

        # Key assertion: handler UUIDs should match baseline
        # If bug exists, they will be shifted by the number of botocore calls
        assert handler_uuid1 == baseline_uuid1, (
            f"Handler UUID should be at generator position 0: {baseline_uuid1}, "
            f"but got {handler_uuid1}. "
            f"Botocore calls tracked: {len(botocore_calls)}. "
            f"Total calls: {freezer.call_count}. "
            "The seeded sequence was shifted by ignored botocore calls!"
        )
        assert handler_uuid2 == baseline_uuid2, (
            f"Handler UUID should be at generator position 1: {baseline_uuid2}, "
            f"but got {handler_uuid2}"
        )
