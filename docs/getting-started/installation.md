# Installation

## Requirements

- Python 3.9 or higher
- pytest 7.0.0 or higher

## Install from PyPI

=== "pip"

    ```bash
    pip install pytest-uuid
    ```

=== "uv"

    ```bash
    uv add pytest-uuid
    ```

=== "poetry"

    ```bash
    poetry add pytest-uuid
    ```

=== "pdm"

    ```bash
    pdm add pytest-uuid
    ```

## Install from Source

```bash
git clone https://github.com/CaptainDriftwood/pytest-uuid.git
cd pytest-uuid
pip install -e .
```

## Verify Installation

After installation, verify that the plugin is registered with pytest:

```bash
pytest --co -q
```

You should see `pytest_uuid` in the list of plugins, or you can check directly:

```bash
python -c "import pytest_uuid; print(pytest_uuid.__version__)"
```

## Next Steps

Head to the [Quick Start](quickstart.md) guide to learn how to use pytest-uuid in your tests.