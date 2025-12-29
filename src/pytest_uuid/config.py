"""Global configuration for pytest-uuid."""

from __future__ import annotations

import contextvars
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pytest_uuid.generators import ExhaustionBehavior

if TYPE_CHECKING:
    import pytest

# TOML parsing - use stdlib on 3.11+, fallback to tomli
if sys.version_info >= (3, 11):
    import tomllib

    TOMLDecodeError = tomllib.TOMLDecodeError
else:
    import tomli as tomllib  # type: ignore[import-not-found]

    TOMLDecodeError = tomllib.TOMLDecodeError


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


# StashKey for storing configuration in pytest.Config
# We use a try/except for compatibility with older pytest versions
try:
    import pytest

    _config_key = pytest.StashKey[PytestUUIDConfig]()  # type: ignore[attr-defined]
    _has_stash = True
except (ImportError, AttributeError):
    _config_key = None  # type: ignore[assignment]
    _has_stash = False

# ContextVar to track the active pytest.Config reference
# This replaces the module-level global and provides proper isolation
_active_pytest_config: contextvars.ContextVar[pytest.Config | None] = (
    contextvars.ContextVar("_active_pytest_config", default=None)
)

# Stack of tokens for nested pytest sessions (e.g., pytester in-process runs)
_config_tokens: list[contextvars.Token[pytest.Config | None]] = []


def get_config() -> PytestUUIDConfig:
    """Get the current configuration from pytest.Config.stash.

    Returns:
        The current PytestUUIDConfig instance.

    Raises:
        RuntimeError: If called outside of a pytest session or if pytest
            doesn't support stash (requires pytest 7.0+).
    """
    pytest_config = _active_pytest_config.get()
    if pytest_config is None:
        raise RuntimeError(
            "pytest-uuid configuration is only available within a pytest session. "
            "Ensure pytest has been configured before accessing config."
        )
    if not (_has_stash and _config_key is not None and hasattr(pytest_config, "stash")):
        raise RuntimeError(
            "pytest-uuid requires pytest with stash support (pytest 7.0+)."
        )
    return pytest_config.stash[_config_key]


def configure(
    *,
    default_ignore_list: list[str] | None = None,
    extend_ignore_list: list[str] | None = None,
    default_exhaustion_behavior: ExhaustionBehavior | str | None = None,
) -> None:
    """Configure pytest-uuid settings in the current pytest session.

    This function allows you to set global defaults that apply to all
    UUID mocking unless overridden at the individual test level.

    Args:
        default_ignore_list: Replace the default ignore list entirely.
            Packages in this list will not have uuid4 patched.
        extend_ignore_list: Add packages to the ignore list without
            replacing the defaults.
        default_exhaustion_behavior: Default behavior when a UUID sequence
            is exhausted. Can be "cycle", "random", or "raise".

    Raises:
        RuntimeError: If called outside of a pytest session.

    Example:
        import pytest_uuid

        pytest_uuid.configure(
            default_ignore_list=["sqlalchemy", "celery"],
            extend_ignore_list=["myapp.internal"],
            default_exhaustion_behavior="raise",
        )
    """
    config = get_config()

    if default_ignore_list is not None:
        config.default_ignore_list = list(default_ignore_list)

    if extend_ignore_list is not None:
        config.extend_ignore_list = list(extend_ignore_list)

    if default_exhaustion_behavior is not None:
        if isinstance(default_exhaustion_behavior, str):
            config.default_exhaustion_behavior = ExhaustionBehavior(
                default_exhaustion_behavior
            )
        else:
            config.default_exhaustion_behavior = default_exhaustion_behavior


def reset_config() -> None:
    """Reset configuration to defaults. Primarily for testing."""
    pytest_config = _active_pytest_config.get()
    if (
        pytest_config is not None
        and _has_stash
        and _config_key is not None
        and hasattr(pytest_config, "stash")
    ):
        pytest_config.stash[_config_key] = PytestUUIDConfig()


def _set_active_pytest_config(config: pytest.Config) -> None:
    """Set the active pytest config reference.

    This is called by pytest_configure to enable config storage in stash.
    Uses a token stack to support nested pytest sessions (e.g., pytester).
    """
    token = _active_pytest_config.set(config)
    _config_tokens.append(token)


def _clear_active_pytest_config() -> None:
    """Restore the previous pytest config reference.

    This is called by pytest_unconfigure for cleanup.
    Restores the previous value from the token stack to support nested sessions.
    """
    if _config_tokens:
        token = _config_tokens.pop()
        _active_pytest_config.reset(token)


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
    except TOMLDecodeError as e:
        warnings.warn(
            f"pytest-uuid: Failed to parse {pyproject_path}: {e}. "
            f"Using default configuration.",
            UserWarning,
            stacklevel=2,
        )
        return {}
    except OSError as e:
        warnings.warn(
            f"pytest-uuid: Failed to read {pyproject_path}: {e}. "
            f"Using default configuration.",
            UserWarning,
            stacklevel=2,
        )
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
