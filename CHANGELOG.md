# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-02-08

### Added

- Python 3.15 support - added to CI test matrix, nox sessions, and pyproject.toml classifiers ([#46](https://github.com/CaptainDriftwood/pytest-uuid/pull/46))

### Changed

- Optimized import hook with module ID caching to avoid redundant scanning ([#46](https://github.com/CaptainDriftwood/pytest-uuid/pull/46))
- Skip patching uuid module directly in import hook since it's already patched by UUIDFreezer ([#46](https://github.com/CaptainDriftwood/pytest-uuid/pull/46))

## [0.5.0] - 2026-02-08

### Added

- `seed` property on `UUIDFreezer`, `UUIDMocker`, and `SeededUUIDGenerator` to expose the active seed value for introspection ([#45](https://github.com/CaptainDriftwood/pytest-uuid/pull/45))

### Fixed

- Ruff lint error (PLC0207) by adding `maxsplit=1` to `str.split()` call in plugin.py

## [0.4.0] - 2026-01-08

### Added

- `caller_line`, `caller_function`, and `caller_qualname` fields to `UUIDCall` dataclass for enhanced call tracking
- Import hook mechanism to handle stale patched uuid4 functions

### Fixed

- Non-deterministic UUID generation when modules import uuid4 during freeze context

### Security

- Bump mkdocs-material minimum version to fix XSS vulnerability ([#30](https://github.com/CaptainDriftwood/pytest-uuid/pull/30))
- Pin GitHub Actions to full-length commit SHAs ([#29](https://github.com/CaptainDriftwood/pytest-uuid/pull/29))

## [0.3.0] - 2026-01-05

### Added

- Add `botocore` to default ignore list for AWS SDK compatibility ([#21](https://github.com/CaptainDriftwood/pytest-uuid/pull/21))
- Integration test infrastructure for third-party library testing ([#21](https://github.com/CaptainDriftwood/pytest-uuid/pull/21))
- MkDocs Material documentation site ([#16](https://github.com/CaptainDriftwood/pytest-uuid/pull/16))
- CodeQL code scanning for security analysis
- GitHub issue templates

## [0.2.0] - 2025-12-29

### Added

- `set_ignore()` method to `mock_uuid` fixture for runtime module exclusion
- Dependabot configuration for GitHub Actions and pip dependencies
- Spy Mode documentation with `spy_uuid` and `mock_uuid.spy()` examples
- Enhanced Call Tracking section with detailed interrogation examples
- Documentation for `set_ignore()` method and Ignoring Modules section

### Fixed

- Detection of aliased uuid4 imports (`from uuid import uuid4 as alias`)
- Python 3.9 compatibility issues

### Changed

- Reorganize test suite into `unit/` and `integration/` directories
- Use `importlib.metadata` for dynamic version (single source of truth)
- Rename plugin entry point from `uuid` to `pytest_uuid`
- Refactor config to use `pytest.Config.stash` with `ContextVar`

## [0.1.0] - 2025-12-26

### Added

- Initial release of pytest-uuid plugin
- Freezegun-inspired API for mocking `uuid.uuid4()` calls
- `mock_uuid` fixture with context manager and decorator support
- `spy_uuid` fixture for observing UUID generation without mocking
- Sequence, random, and callable UUID generators
- Call tracking with `UUIDCall` dataclass
- Module ignore configuration via `pyproject.toml` or `pytest.ini`
- Python 3.9, 3.10, 3.11, 3.12, 3.13, and 3.14 support

[Unreleased]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/CaptainDriftwood/pytest-uuid/releases/tag/v0.1.0
