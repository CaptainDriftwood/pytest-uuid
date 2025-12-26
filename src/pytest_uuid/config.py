"""Global configuration for pytest-uuid."""

from __future__ import annotations

from dataclasses import dataclass, field

from pytest_uuid.generators import ExhaustionBehavior


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


# Global configuration instance
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
