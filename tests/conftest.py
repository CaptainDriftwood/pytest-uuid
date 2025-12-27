"""Pytest configuration for pytest-uuid tests."""

import pytest

from pytest_uuid.config import reset_config

# Enable pytester plugin for testing pytest plugins
pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def reset_pytest_uuid_config():
    """Reset pytest-uuid global config before and after each test."""
    reset_config()
    yield
    reset_config()
