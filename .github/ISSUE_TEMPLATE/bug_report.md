---
name: Bug Report
about: Report a bug or unexpected behavior
title: ''
labels: bug
assignees: ''
---

**pytest-uuid version**
**Environment**
- Python version:
- pytest version:
- OS:

**Which API are you using?**
- [ ] `mock_uuid` fixture
- [ ] `spy_uuid` fixture
- [ ] `@freeze_uuid` decorator
- [ ] `@pytest.mark.freeze_uuid` marker
- [ ] `freeze_uuid` context manager

**Description**
A clear description of the bug.

**Minimal Reproducible Example**
```python
# Paste a minimal test that reproduces the issue
import uuid

def test_example(mock_uuid):
    mock_uuid.set("...")
    # ...
