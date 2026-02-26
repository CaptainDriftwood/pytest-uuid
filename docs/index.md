# pytest-uuid

<p align="center">
  <img src="images/logo.svg" alt="pytest-uuid logo" width="365">
</p>

A pytest plugin for mocking UUID generation in your tests. Supports uuid1, uuid3, uuid4, uuid5, uuid6, uuid7, and uuid8.

[![PyPI version](https://img.shields.io/pypi/v/pytest-uuid.svg)](https://pypi.org/project/pytest-uuid/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://github.com/CaptainDriftwood/pytest-uuid/actions/workflows/test.yml/badge.svg)](https://github.com/CaptainDriftwood/pytest-uuid/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/CaptainDriftwood/pytest-uuid/graph/badge.svg)](https://codecov.io/gh/CaptainDriftwood/pytest-uuid)

## Features

- Mock all UUID versions: uuid1, uuid3, uuid4, uuid5, uuid6, uuid7, uuid8
- Works with both `import uuid` and `from uuid import uuid4` patterns
- Multiple ways to mock: static, sequence, seeded, or node-seeded
- Decorator, marker, and fixture APIs (inspired by freezegun)
- Configurable exhaustion behavior for sequences
- Ignore list for packages that should use real UUIDs
- Spy mode to track calls without mocking
- Detailed call tracking with caller module/file info
- Automatic cleanup after each test
- Zero configuration required - just use the fixture
- uuid6/uuid7/uuid8 support via [uuid6](https://pypi.org/project/uuid6/) backport (Python < 3.14)

## Quick Example

```python
import uuid

def test_single_uuid(mock_uuid):
    mock_uuid.uuid4.set("12345678-1234-4678-8234-567812345678")
    assert str(uuid.uuid4()) == "12345678-1234-4678-8234-567812345678"

def test_multiple_uuids(mock_uuid):
    mock_uuid.uuid4.set(
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    )
    assert str(uuid.uuid4()) == "11111111-1111-4111-8111-111111111111"
    assert str(uuid.uuid4()) == "22222222-2222-4222-8222-222222222222"
```

## Installation

```bash
pip install pytest-uuid

# or with uv
uv add pytest-uuid
```

## Next Steps

- [Installation](getting-started/installation.md) - Detailed installation instructions
- [Quick Start](getting-started/quickstart.md) - Get up and running quickly
- [User Guide](guide/fixture-api.md) - Learn about all the APIs
- [API Reference](api-reference.md) - Complete API documentation