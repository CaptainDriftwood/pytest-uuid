"""Isolated conftest for reproducing the late import bug.

This conftest sets up freeze_uuid as an autouse fixture to demonstrate
that modules imported AFTER freeze_uuid starts are not patched when
they use `from uuid import uuid4`.
"""

import hashlib

import pytest

from pytest_uuid import freeze_uuid


@pytest.fixture(autouse=True)
def freeze_uuids_for_test(request):
    """Freeze UUIDs with a deterministic seed based on test node ID.

    This mimics a real-world setup where UUIDs should be deterministic
    for snapshot testing. The bug manifests when a module using
    `from uuid import uuid4` is imported INSIDE a test function.
    """
    seed = int(hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16], 16)
    with freeze_uuid(seed=seed) as freezer:
        yield freezer
