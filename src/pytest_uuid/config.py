"""Global configuration for pytest-uuid."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pytest_uuid.generators import ExhaustionBehavior

# TOML parsing - use stdlib on 3.11+, fallback to tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


@dataclass
class PytestUUIDConfig:
    """Global configuration for pytest-uuid.

    This class manages global settings that apply to all UUID mocking
    unless overridden at the individual test/decorator level.
    """

    # Default packages to ignore when patching uuid4
    # These packages will continue to use real uuid.uuid4()
    default_ignore_list: list[str] = field(default_factory=list)

    # Additional packages to ignore (extends default_ignore_list)
    extend_ignore_list: list[str] = field(default_factory=list)

    # Default behavior when UUID sequence is exhausted
    default_exhaustion_behavior: ExhaustionBehavior = ExhaustionBehavior.CYCLE

    def get_ignore_list(self) -> tuple[str, ...]:
        """Get the combined ignore list as a tuple."""
        return tuple(self.default_ignore_list + self.extend_ignore_list)


_config: PytestUUIDConfig = PytestUUIDConfig()


def configure(
    *,
    default_ignore_list: list[str] | None = None,
    extend_ignore_list: list[str] | None = None,
    default_exhaustion_behavior: ExhaustionBehavior | str | None = None,
) -> None:
    """Configure global pytest-uuid settings.

    This function allows you to set global defaults that apply to all
    UUID mocking unless overridden at the individual test level.

    Args:
        default_ignore_list: Replace the default ignore list entirely.
            Packages in this list will not have uuid4 patched.
        extend_ignore_list: Add packages to the ignore list without
            replacing the defaults.
        default_exhaustion_behavior: Default behavior when a UUID sequence
            is exhausted. Can be "cycle", "random", or "raise".

    Example:
        import pytest_uuid

        pytest_uuid.configure(
            default_ignore_list=["sqlalchemy", "celery"],
            extend_ignore_list=["myapp.internal"],
            default_exhaustion_behavior="raise",
        )
    """
    global _config

    if default_ignore_list is not None:
        _config.default_ignore_list = list(default_ignore_list)

    if extend_ignore_list is not None:
        _config.extend_ignore_list = list(extend_ignore_list)

    if default_exhaustion_behavior is not None:
        if isinstance(default_exhaustion_behavior, str):
            _config.default_exhaustion_behavior = ExhaustionBehavior(
                default_exhaustion_behavior
            )
        else:
            _config.default_exhaustion_behavior = default_exhaustion_behavior


def get_config() -> PytestUUIDConfig:
    """Get the current global configuration."""
    return _config


def reset_config() -> None:
    """Reset configuration to defaults. Primarily for testing."""
    global _config
    _config = PytestUUIDConfig()


def _load_pyproject_config(rootdir: Path | None = None) -> dict[str, Any]:
    """Load pytest-uuid config from pyproject.toml.

    Args:
        rootdir: Directory to search for pyproject.toml.
                 If None, uses current working directory.

    Returns:
        Configuration dict from [tool.pytest_uuid] section,
        or empty dict if not found.
    """
    if rootdir is None:
        rootdir = Path.cwd()

    pyproject_path = rootdir / "pyproject.toml"
    if not pyproject_path.exists():
        return {}

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("tool", {}).get("pytest_uuid", {})
    except Exception:
        # Silently ignore parse errors - don't break pytest
        return {}


def load_config_from_pyproject(rootdir: Path | None = None) -> None:
    """Load configuration from pyproject.toml and apply it.

    This function reads the [tool.pytest_uuid] section from pyproject.toml
    and applies the settings to the global configuration.

    Supported keys:
        - default_ignore_list: List of module prefixes to ignore
        - extend_ignore_list: Additional modules to ignore
        - default_exhaustion_behavior: "cycle", "random", or "raise"

    Args:
        rootdir: Directory containing pyproject.toml.

    Example pyproject.toml:
        [tool.pytest_uuid]
        default_ignore_list = ["sqlalchemy", "celery"]
        extend_ignore_list = ["myapp.internal"]
        default_exhaustion_behavior = "raise"
    """
    config_data = _load_pyproject_config(rootdir)
    if not config_data:
        return

    configure(
        default_ignore_list=config_data.get("default_ignore_list"),
        extend_ignore_list=config_data.get("extend_ignore_list"),
        default_exhaustion_behavior=config_data.get("default_exhaustion_behavior"),
    )
