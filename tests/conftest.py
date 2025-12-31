"""Pytest configuration for pytest-uuid tests."""

import pytest

from pytest_uuid.config import (
    PytestUUIDConfig,
    _config_key,
    _has_stash,
    reset_config,
)

# Enable pytester plugin for integration tests
pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def reset_pytest_uuid_config(request):
    """Reset pytest-uuid config before and after each test.

    This ensures tests don't pollute each other's configuration state.
    """
    # Reset stash directly for immediate effect
    if _has_stash and _config_key is not None and hasattr(request.config, "stash"):
        request.config.stash[_config_key] = PytestUUIDConfig()

    reset_config()
    yield
    reset_config()
