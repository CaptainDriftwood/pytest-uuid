"""Tests for pytest-uuid configuration."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytest_uuid.config import (
    DEFAULT_IGNORE_PACKAGES,
    PytestUUIDConfig,
    _load_pyproject_config,
    configure,
    get_config,
    load_config_from_pyproject,
    reset_config,
)
from pytest_uuid.generators import ExhaustionBehavior

# --- PytestUUIDConfig ---


def test_config_default_values():
    """Test default configuration values."""
    config = PytestUUIDConfig()

    assert config.default_ignore_list == list(DEFAULT_IGNORE_PACKAGES)
    assert config.extend_ignore_list == []
    assert config.default_exhaustion_behavior == ExhaustionBehavior.CYCLE


def test_config_get_ignore_list_combines_lists():
    """Test that get_ignore_list combines both lists."""
    config = PytestUUIDConfig(
        default_ignore_list=["pkg1", "pkg2"],
        extend_ignore_list=["pkg3"],
    )

    result = config.get_ignore_list()
    assert result == ("pkg1", "pkg2", "pkg3")


def test_config_get_ignore_list_defaults():
    """Test get_ignore_list returns default packages."""
    config = PytestUUIDConfig()
    assert config.get_ignore_list() == tuple(DEFAULT_IGNORE_PACKAGES)


@pytest.mark.botocore
def test_botocore_in_default_ignore_packages():
    """Verify botocore is included in the default ignore list.

    botocore uses uuid.uuid4() internally for generating idempotent
    ClientTokens in AWS API operations. Patching this can interfere
    with AWS SDK retry logic and idempotency guarantees.
    """
    assert "botocore" in DEFAULT_IGNORE_PACKAGES


# --- configure ---


def test_configure_default_ignore_list():
    """Test setting default_ignore_list."""
    configure(default_ignore_list=["sqlalchemy", "celery"])

    config = get_config()
    assert config.default_ignore_list == ["sqlalchemy", "celery"]


def test_configure_extend_ignore_list():
    """Test setting extend_ignore_list."""
    configure(extend_ignore_list=["myapp.internal"])

    config = get_config()
    assert config.extend_ignore_list == ["myapp.internal"]


def test_configure_exhaustion_behavior_as_string():
    """Test setting exhaustion behavior with a string."""
    configure(default_exhaustion_behavior="raise")

    config = get_config()
    assert config.default_exhaustion_behavior == ExhaustionBehavior.RAISE


def test_configure_exhaustion_behavior_as_enum():
    """Test setting exhaustion behavior with enum."""
    configure(default_exhaustion_behavior=ExhaustionBehavior.RANDOM)

    config = get_config()
    assert config.default_exhaustion_behavior == ExhaustionBehavior.RANDOM


def test_configure_multiple_options():
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


def test_configure_preserves_unset_values():
    """Test that configure only modifies specified values."""
    configure(default_ignore_list=["pkg1"])
    configure(extend_ignore_list=["pkg2"])

    config = get_config()
    assert config.default_ignore_list == ["pkg1"]
    assert config.extend_ignore_list == ["pkg2"]


def test_configure_none_values_are_ignored():
    """Test that None values don't change existing config."""
    configure(default_ignore_list=["pkg1"])
    configure(default_ignore_list=None)  # Should not change

    config = get_config()
    assert config.default_ignore_list == ["pkg1"]


# --- reset_config ---


def test_reset_config_restores_defaults():
    """Test that reset_config restores all defaults."""
    configure(
        default_ignore_list=["pkg1"],
        extend_ignore_list=["pkg2"],
        default_exhaustion_behavior="raise",
    )

    reset_config()
    config = get_config()

    assert config.default_ignore_list == list(DEFAULT_IGNORE_PACKAGES)
    assert config.extend_ignore_list == []
    assert config.default_exhaustion_behavior == ExhaustionBehavior.CYCLE


# --- get_config ---


def test_get_config_returns_same_instance():
    """Test that get_config returns the same instance."""
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2


# --- pyproject.toml loading ---


def test_pyproject_load_nonexistent_file(tmp_path: Path):
    """Test loading from directory without pyproject.toml."""
    result = _load_pyproject_config(tmp_path)
    assert result == {}


def test_pyproject_load_empty_file(tmp_path: Path):
    """Test loading from empty pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("")

    result = _load_pyproject_config(tmp_path)
    assert result == {}


def test_pyproject_load_without_tool_section(tmp_path: Path):
    """Test loading from pyproject.toml without [tool] section."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"\n')

    result = _load_pyproject_config(tmp_path)
    assert result == {}


def test_pyproject_load_without_pytest_uuid_section(tmp_path: Path):
    """Test loading from pyproject.toml without [tool.pytest_uuid]."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[tool.other]\nkey = "value"\n')

    result = _load_pyproject_config(tmp_path)
    assert result == {}


def test_pyproject_load_with_full_config(tmp_path: Path):
    """Test loading full configuration."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.pytest_uuid]
default_ignore_list = ["sqlalchemy", "celery"]
extend_ignore_list = ["myapp.internal"]
default_exhaustion_behavior = "raise"
"""
    )

    result = _load_pyproject_config(tmp_path)

    assert result["default_ignore_list"] == ["sqlalchemy", "celery"]
    assert result["extend_ignore_list"] == ["myapp.internal"]
    assert result["default_exhaustion_behavior"] == "raise"


def test_pyproject_load_applies_config(tmp_path: Path):
    """Test that load_config_from_pyproject applies settings."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.pytest_uuid]
default_ignore_list = ["pkg1"]
default_exhaustion_behavior = "random"
"""
    )

    load_config_from_pyproject(tmp_path)
    config = get_config()

    assert config.default_ignore_list == ["pkg1"]
    assert config.default_exhaustion_behavior == ExhaustionBehavior.RANDOM


def test_pyproject_invalid_toml_warns_and_uses_defaults(tmp_path: Path):
    """Test that invalid TOML emits a warning and uses defaults."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("invalid [ toml content")

    # Should not raise, but should warn
    with pytest.warns(UserWarning, match="Failed to parse"):
        result = _load_pyproject_config(tmp_path)
    assert result == {}


def test_pyproject_programmatic_config_overrides_file(tmp_path: Path):
    """Test that programmatic configure() overrides file config."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.pytest_uuid]
default_ignore_list = ["from_file"]
"""
    )

    load_config_from_pyproject(tmp_path)
    configure(default_ignore_list=["programmatic"])

    config = get_config()
    assert config.default_ignore_list == ["programmatic"]


def test_pyproject_load_partial_config(tmp_path: Path):
    """Test loading partial configuration."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.pytest_uuid]
extend_ignore_list = ["only_extend"]
"""
    )

    load_config_from_pyproject(tmp_path)
    config = get_config()

    # Only extend_ignore_list should be set
    assert config.extend_ignore_list == ["only_extend"]
    # Others should remain defaults
    assert config.default_ignore_list == list(DEFAULT_IGNORE_PACKAGES)
    assert config.default_exhaustion_behavior == ExhaustionBehavior.CYCLE
