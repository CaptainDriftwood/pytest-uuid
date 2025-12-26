"""Tests for pytest-uuid configuration."""

from __future__ import annotations

import pytest

from pytest_uuid.config import (
    PytestUUIDConfig,
    configure,
    get_config,
    reset_config,
)
from pytest_uuid.generators import ExhaustionBehavior


@pytest.fixture(autouse=True)
def reset_config_after_test():
    """Reset config after each test to avoid pollution."""
    yield
    reset_config()


class TestPytestUUIDConfig:
    """Tests for PytestUUIDConfig class."""

    def test_default_values(self):
        """Test default configuration values."""
        config = PytestUUIDConfig()

        assert config.default_ignore_list == []
        assert config.extend_ignore_list == []
        assert config.default_exhaustion_behavior == ExhaustionBehavior.CYCLE

    def test_get_ignore_list_combines_lists(self):
        """Test that get_ignore_list combines both lists."""
        config = PytestUUIDConfig(
            default_ignore_list=["pkg1", "pkg2"],
            extend_ignore_list=["pkg3"],
        )

        result = config.get_ignore_list()
        assert result == ("pkg1", "pkg2", "pkg3")

    def test_get_ignore_list_empty(self):
        """Test get_ignore_list with empty lists."""
        config = PytestUUIDConfig()
        assert config.get_ignore_list() == ()


class TestConfigure:
    """Tests for the configure function."""

    def test_configure_default_ignore_list(self):
        """Test setting default_ignore_list."""
        configure(default_ignore_list=["sqlalchemy", "celery"])

        config = get_config()
        assert config.default_ignore_list == ["sqlalchemy", "celery"]

    def test_configure_extend_ignore_list(self):
        """Test setting extend_ignore_list."""
        configure(extend_ignore_list=["myapp.internal"])

        config = get_config()
        assert config.extend_ignore_list == ["myapp.internal"]

    def test_configure_exhaustion_behavior_as_string(self):
        """Test setting exhaustion behavior with a string."""
        configure(default_exhaustion_behavior="raise")

        config = get_config()
        assert config.default_exhaustion_behavior == ExhaustionBehavior.RAISE

    def test_configure_exhaustion_behavior_as_enum(self):
        """Test setting exhaustion behavior with enum."""
        configure(default_exhaustion_behavior=ExhaustionBehavior.RANDOM)

        config = get_config()
        assert config.default_exhaustion_behavior == ExhaustionBehavior.RANDOM

    def test_configure_multiple_options(self):
        """Test setting multiple options at once."""
        configure(
            default_ignore_list=["pkg1"],
            extend_ignore_list=["pkg2"],
            default_exhaustion_behavior="random",
        )

        config = get_config()
        assert config.default_ignore_list == ["pkg1"]
        assert config.extend_ignore_list == ["pkg2"]
        assert config.default_exhaustion_behavior == ExhaustionBehavior.RANDOM

    def test_configure_preserves_unset_values(self):
        """Test that configure only modifies specified values."""
        configure(default_ignore_list=["pkg1"])
        configure(extend_ignore_list=["pkg2"])

        config = get_config()
        assert config.default_ignore_list == ["pkg1"]
        assert config.extend_ignore_list == ["pkg2"]

    def test_configure_none_values_are_ignored(self):
        """Test that None values don't change existing config."""
        configure(default_ignore_list=["pkg1"])
        configure(default_ignore_list=None)  # Should not change

        config = get_config()
        assert config.default_ignore_list == ["pkg1"]


class TestResetConfig:
    """Tests for reset_config function."""

    def test_reset_restores_defaults(self):
        """Test that reset_config restores all defaults."""
        configure(
            default_ignore_list=["pkg1"],
            extend_ignore_list=["pkg2"],
            default_exhaustion_behavior="raise",
        )

        reset_config()
        config = get_config()

        assert config.default_ignore_list == []
        assert config.extend_ignore_list == []
        assert config.default_exhaustion_behavior == ExhaustionBehavior.CYCLE


class TestGetConfig:
    """Tests for get_config function."""

    def test_returns_same_instance(self):
        """Test that get_config returns the same instance."""
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2
