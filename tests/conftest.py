"""Pytest configuration for pytest-uuid tests."""

import pytest

from pytest_uuid.config import reset_config

# Enable pytester plugin for integration tests
pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def reset_pytest_uuid_config():
    """Reset pytest-uuid global config before and after each test.

    This ensures tests don't pollute each other's configuration state.
    """
    reset_config()
    yield
    reset_config()
