# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-27

### Added

- Multi-UUID version support: mock uuid1, uuid4, uuid6, uuid7, uuid8; spy-only tracking for uuid3 and uuid5
- Version-specific freeze functions: `freeze_uuid4`, `freeze_uuid1`, `freeze_uuid6`, `freeze_uuid7`, `freeze_uuid8`
- Version-specific pytest markers: `@pytest.mark.freeze_uuid4`, `@pytest.mark.freeze_uuid1`, etc.
- `UUIDMocker` container class with sub-mockers for each UUID version (`mock_uuid.uuid4`, `mock_uuid.uuid1`, etc.)
- `NamespaceUUIDSpy` for tracking uuid3/uuid5 calls without mocking (deterministic hash-based UUIDs)
- `node` and `clock_seq` parameters for uuid1/uuid6 to control time-based UUID components
- Thread-safe call tracking: `call_count`, `calls`, `generated_uuids`, and related properties now use per-instance locks for safe concurrent access from multiple threads
- `NamespaceUUIDCall` dataclass for uuid3/uuid5 call tracking with `namespace` and `name` fields
- `uuid_version` field on `UUIDCall` dataclass to identify which UUID version was called

### Changed

- **BREAKING**: `mock_uuid` fixture now requires explicit version access via properties (e.g., `mock_uuid.uuid4.set(...)` instead of `mock_uuid.set(...)`)
- **BREAKING**: `freeze_uuid()` is now a deprecated alias for `freeze_uuid4()`; use version-specific functions instead
- Replaced import hook with permanent proxy approach for UUID mocking
- Simplified architecture: proxy installs once at plugin load, no per-import patching
- Improved thread safety with lock-protected generator stack

### Fixed

- Pydantic `default_factory=uuid4` now works correctly (proxy captured at class definition time)
- Eliminated stale patched function issues with late imports
- Resolved edge cases where modules imported during freeze context had non-deterministic UUIDs

### Removed

- `_import_hook.py` module (internal, replaced by `_proxy.py`)

### Migration Guide

**mock_uuid fixture changes:**
```python
# Before (0.6.x)
mock_uuid.set("12345678-1234-4678-8234-567812345678")
mock_uuid.call_count

# After (1.0.0+)
mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
mock_uuid.uuid4.call_count
```

**freeze_uuid decorator changes:**
```python
# Before (0.6.x)
@freeze_uuid("12345678-1234-4678-8234-567812345678")

# After (1.0.0+) - use version-specific function
@freeze_uuid4("12345678-1234-4678-8234-567812345678")
```

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

[Unreleased]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.6.0...v1.0.0
[0.6.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/CaptainDriftwood/pytest-uuid/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/CaptainDriftwood/pytest-uuid/releases/tag/v0.1.0
