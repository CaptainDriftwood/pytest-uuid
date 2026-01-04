"""Integration tests for installed package isolation using pytest-venv.

These tests create real virtual environments, install pytest-uuid and a test
package, then run pytest inside the venv to verify mock isolation works
correctly with truly installed packages.

These tests are marked as 'slow' since venv creation and pip installs take time.
Run with: pytest -m slow
Skip with: pytest -m "not slow"
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

# Path to the pytest-uuid source and test fixture package
PYTEST_UUID_ROOT = Path(__file__).parent.parent.parent
UUID_TESTPKG_PATH = PYTEST_UUID_ROOT / "tests" / "fixtures" / "uuid_testpkg"


@pytest.fixture
def venv_with_packages(venv):
    """Create a venv with pytest-uuid and uuid-testpkg installed."""
    venv.create()

    # Install pytest-uuid from local source (editable)
    venv.install(str(PYTEST_UUID_ROOT), editable=True)

    # Install the test fixture package
    venv.install(str(UUID_TESTPKG_PATH))

    # Install pytest-xdist for parallel testing
    venv.install("pytest-xdist")

    return venv


def write_test_files(test_dir: Path, test_content: str, conftest_content=None):
    """Write test files to the given directory."""
    test_dir.mkdir(parents=True, exist_ok=True)

    if conftest_content:
        (test_dir / "conftest.py").write_text(conftest_content)

    (test_dir / "test_isolation.py").write_text(test_content)


def run_pytest_in_venv(
    venv, test_dir: Path, *extra_args
) -> subprocess.CompletedProcess:
    """Run pytest inside the venv and return the result."""
    cmd = [
        str(venv.python),
        "-m",
        "pytest",
        str(test_dir),
        "-v",
        "--tb=short",
        *extra_args,
    ]
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        cwd=str(test_dir),
    )


# --- Sequential execution tests ---


@pytest.mark.slow
def test_installed_pkg_mock_isolation_sequential(venv_with_packages, tmp_path):
    """Test mock isolation with installed package in sequential mode.

    Verifies that mocks don't leak between tests when using an installed package.
    """
    test_content = textwrap.dedent('''
        """Test mock isolation with installed uuid_testpkg."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id, UUIDService

        results = {}

        @freeze_uuid("11111111-1111-1111-1111-111111111111")
        def test_01_with_mocking():
            """First test uses mocking."""
            result = generate_id()
            results["test_01"] = str(result)
            assert str(result) == "11111111-1111-1111-1111-111111111111"

            service = UUIDService()
            assert str(service.create_id()) == "11111111-1111-1111-1111-111111111111"

        def test_02_without_mocking():
            """Second test has NO mocking - should get real UUIDs."""
            result = generate_id()
            results["test_02"] = str(result)
            assert str(result) != "11111111-1111-1111-1111-111111111111"
            assert result.version == 4

        @freeze_uuid("22222222-2222-2222-2222-222222222222")
        def test_03_with_different_mock():
            """Third test uses different mock."""
            result = generate_id()
            results["test_03"] = str(result)
            assert str(result) == "22222222-2222-2222-2222-222222222222"

        def test_04_without_mocking_again():
            """Fourth test has NO mocking - verify no leakage."""
            result = generate_id()
            results["test_04"] = str(result)
            assert str(result) != "11111111-1111-1111-1111-111111111111"
            assert str(result) != "22222222-2222-2222-2222-222222222222"
            assert result.version == 4

        def test_05_verify():
            """Verify all results."""
            assert results["test_01"] == "11111111-1111-1111-1111-111111111111"
            assert results["test_02"] != "11111111-1111-1111-1111-111111111111"
            assert results["test_03"] == "22222222-2222-2222-2222-222222222222"
            assert results["test_04"] != "22222222-2222-2222-2222-222222222222"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "5 passed" in result.stdout


@pytest.mark.slow
def test_installed_pkg_alt_service_sequential(venv_with_packages, tmp_path):
    """Test mock isolation with 'import uuid' pattern (alt_service)."""
    test_content = textwrap.dedent('''
        """Test mock isolation with alt_service (import uuid pattern)."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import alt_generate_id, AltUUIDService

        results = {}

        @freeze_uuid("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        def test_01_mocked():
            result = alt_generate_id()
            results["test_01"] = str(result)
            assert str(result) == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

        def test_02_not_mocked():
            result = alt_generate_id()
            results["test_02"] = str(result)
            assert str(result) != "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            assert result.version == 4

        def test_03_verify():
            assert results["test_01"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            assert results["test_02"] != "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "3 passed" in result.stdout


@pytest.mark.slow
def test_installed_pkg_first_unmocked_then_mocked(venv_with_packages, tmp_path):
    """Test: first test unmocked, second mocked, third unmocked.

    This verifies that a module imported and used without mocking
    can be properly mocked in a subsequent test.
    """
    test_content = textwrap.dedent('''
        """Test unmocked -> mocked -> unmocked sequence."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id

        results = {}

        def test_01_no_mocking():
            """First test has NO mocking."""
            result = generate_id()
            results["test_01"] = str(result)
            assert result.version == 4

        @freeze_uuid("34343434-3434-3434-3434-343434343434")
        def test_02_with_mocking():
            """Second test uses mocking."""
            result = generate_id()
            results["test_02"] = str(result)
            assert str(result) == "34343434-3434-3434-3434-343434343434"

        def test_03_no_mocking_again():
            """Third test has NO mocking."""
            result = generate_id()
            results["test_03"] = str(result)
            assert str(result) != "34343434-3434-3434-3434-343434343434"
            assert result.version == 4

        def test_04_verify():
            assert results["test_01"] != "34343434-3434-3434-3434-343434343434"
            assert results["test_02"] == "34343434-3434-3434-3434-343434343434"
            assert results["test_03"] != "34343434-3434-3434-3434-343434343434"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "4 passed" in result.stdout


# --- Parallel execution tests (xdist) ---


@pytest.mark.slow
@pytest.mark.parallel
def test_installed_pkg_mock_isolation_parallel(venv_with_packages, tmp_path):
    """Test mock isolation with installed package in parallel mode (-n auto).

    Each xdist worker should have proper isolation.
    """
    test_content = textwrap.dedent('''
        """Test mock isolation in parallel execution."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id

        @freeze_uuid("11111111-1111-1111-1111-111111111111")
        def test_worker_a_mocked():
            result = generate_id()
            assert str(result) == "11111111-1111-1111-1111-111111111111"

        @freeze_uuid("22222222-2222-2222-2222-222222222222")
        def test_worker_b_mocked():
            result = generate_id()
            assert str(result) == "22222222-2222-2222-2222-222222222222"

        def test_worker_c_not_mocked():
            result = generate_id()
            assert str(result) != "11111111-1111-1111-1111-111111111111"
            assert str(result) != "22222222-2222-2222-2222-222222222222"
            assert result.version == 4

        @freeze_uuid("33333333-3333-3333-3333-333333333333")
        def test_worker_d_mocked():
            result = generate_id()
            assert str(result) == "33333333-3333-3333-3333-333333333333"

        def test_worker_e_not_mocked():
            result = generate_id()
            assert result.version == 4

        @freeze_uuid("44444444-4444-4444-4444-444444444444")
        def test_worker_f_mocked():
            result = generate_id()
            assert str(result) == "44444444-4444-4444-4444-444444444444"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    # Run with xdist parallel mode
    result = run_pytest_in_venv(venv_with_packages, test_dir, "-n", "auto")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "6 passed" in result.stdout


@pytest.mark.slow
@pytest.mark.parallel
def test_installed_pkg_parallel_many_workers(venv_with_packages, tmp_path):
    """Test with many tests distributed across workers."""
    # Generate many tests to ensure good worker distribution
    test_funcs = []
    for i in range(20):
        if i % 3 == 0:
            # Mocked test
            uuid_val = f"{i:08x}-{i:04x}-{i:04x}-{i:04x}-{i:012x}"
            test_funcs.append(f'''
@freeze_uuid("{uuid_val}")
def test_{i:02d}_mocked():
    result = generate_id()
    assert str(result) == "{uuid_val}"
''')
        else:
            # Unmocked test
            test_funcs.append(f"""
def test_{i:02d}_not_mocked():
    result = generate_id()
    assert result.version == 4
""")

    test_content = textwrap.dedent('''
        """Many tests for parallel distribution."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id
    ''') + "\n".join(test_funcs)

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-n", "4")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "20 passed" in result.stdout


# --- Module-level conftest import tests ---


@pytest.mark.slow
def test_installed_pkg_conftest_module_import(venv_with_packages, tmp_path):
    """Test when conftest.py imports the package at module level.

    This tests the scenario where the package is imported before any
    test runs, potentially caching the module in sys.modules.
    """
    conftest_content = textwrap.dedent('''
        """Conftest that imports uuid_testpkg at module level."""
        import pytest
        from uuid_testpkg import generate_id, UUIDService

        # Module-level import - this happens before any test runs
        # and caches the module in sys.modules

        @pytest.fixture
        def uuid_service():
            """Provide a UUIDService instance."""
            return UUIDService(prefix="test")
    ''')

    test_content = textwrap.dedent('''
        """Tests with module-level conftest import."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id

        results = {}

        @freeze_uuid("55555555-5555-5555-5555-555555555555")
        def test_01_mocked_after_conftest_import():
            """Test mocking works even after conftest imported the module."""
            result = generate_id()
            results["test_01"] = str(result)
            assert str(result) == "55555555-5555-5555-5555-555555555555"

        def test_02_not_mocked():
            """Verify no leakage after mocked test."""
            result = generate_id()
            results["test_02"] = str(result)
            assert str(result) != "55555555-5555-5555-5555-555555555555"
            assert result.version == 4

        @freeze_uuid("66666666-6666-6666-6666-666666666666")
        def test_03_mocked_with_fixture(uuid_service):
            """Test mocking works with fixture from conftest."""
            result = uuid_service.create_id()
            results["test_03"] = str(result)
            assert str(result) == "66666666-6666-6666-6666-666666666666"

        def test_04_not_mocked_with_fixture(uuid_service):
            """Verify fixture works without mocking."""
            result = uuid_service.create_id()
            results["test_04"] = str(result)
            assert str(result) != "66666666-6666-6666-6666-666666666666"
            assert result.version == 4

        def test_05_verify():
            assert results["test_01"] == "55555555-5555-5555-5555-555555555555"
            assert results["test_02"] != "55555555-5555-5555-5555-555555555555"
            assert results["test_03"] == "66666666-6666-6666-6666-666666666666"
            assert results["test_04"] != "66666666-6666-6666-6666-666666666666"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content, conftest_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "5 passed" in result.stdout


@pytest.mark.slow
@pytest.mark.parallel
def test_installed_pkg_conftest_import_parallel(venv_with_packages, tmp_path):
    """Test conftest module import with parallel execution."""
    conftest_content = textwrap.dedent('''
        """Conftest with module-level import."""
        from uuid_testpkg import generate_id, UUIDService
    ''')

    test_content = textwrap.dedent('''
        """Parallel tests with conftest import."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id

        @freeze_uuid("77777777-7777-7777-7777-777777777777")
        def test_a_mocked():
            assert str(generate_id()) == "77777777-7777-7777-7777-777777777777"

        def test_b_not_mocked():
            assert generate_id().version == 4

        @freeze_uuid("88888888-8888-8888-8888-888888888888")
        def test_c_mocked():
            assert str(generate_id()) == "88888888-8888-8888-8888-888888888888"

        def test_d_not_mocked():
            assert generate_id().version == 4
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content, conftest_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-n", "auto")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "4 passed" in result.stdout


# --- Ignore list tests ---


@pytest.mark.slow
def test_installed_pkg_ignore_list(venv_with_packages, tmp_path):
    """Test ignore list works with installed packages."""
    test_content = textwrap.dedent('''
        """Test ignore list with installed package."""
        import uuid
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id

        def test_ignore_installed_package():
            """Test that ignore list works with installed uuid_testpkg."""
            with freeze_uuid(
                "99999999-9999-9999-9999-999999999999",
                ignore=["uuid_testpkg"]
            ):
                # Direct uuid.uuid4() should be mocked
                direct = uuid.uuid4()
                assert str(direct) == "99999999-9999-9999-9999-999999999999"

                # uuid_testpkg should be ignored - returns real UUID
                from_pkg = generate_id()
                assert str(from_pkg) != "99999999-9999-9999-9999-999999999999"
                assert from_pkg.version == 4
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir)

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "1 passed" in result.stdout


@pytest.mark.slow
def test_installed_pkg_ignore_submodule(venv_with_packages, tmp_path):
    """Test ignoring specific submodule of installed package."""
    test_content = textwrap.dedent('''
        """Test ignoring specific submodule."""
        import uuid
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg.service import generate_id as service_gen
        from uuid_testpkg.alt_service import alt_generate_id

        def test_ignore_service_not_alt():
            """Ignore service module but not alt_service."""
            with freeze_uuid(
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                ignore=["uuid_testpkg.service"]
            ):
                # Direct should be mocked
                direct = uuid.uuid4()
                assert str(direct) == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

                # service should be ignored
                from_service = service_gen()
                assert str(from_service) != "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

                # alt_service should be mocked (not in ignore list)
                from_alt = alt_generate_id()
                assert str(from_alt) == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir)

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "1 passed" in result.stdout


# --- Alternating mocked/unmocked stress test ---


@pytest.mark.slow
def test_installed_pkg_alternating_many_times(venv_with_packages, tmp_path):
    """Stress test with many alternations between mocked and unmocked."""
    test_content = textwrap.dedent('''
        """Alternating mocked/unmocked stress test."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id

        results = []
        MOCKED_UUIDS = []

        @freeze_uuid("10101010-1010-1010-1010-101010101010")
        def test_01_mocked():
            MOCKED_UUIDS.append("10101010-1010-1010-1010-101010101010")
            result = generate_id()
            results.append(("test_01", str(result), True))
            assert str(result) == "10101010-1010-1010-1010-101010101010"

        def test_02_unmocked():
            result = generate_id()
            results.append(("test_02", str(result), False))
            assert str(result) not in MOCKED_UUIDS

        @freeze_uuid("20202020-2020-2020-2020-202020202020")
        def test_03_mocked():
            MOCKED_UUIDS.append("20202020-2020-2020-2020-202020202020")
            result = generate_id()
            results.append(("test_03", str(result), True))
            assert str(result) == "20202020-2020-2020-2020-202020202020"

        def test_04_unmocked():
            result = generate_id()
            results.append(("test_04", str(result), False))
            assert str(result) not in MOCKED_UUIDS

        @freeze_uuid("30303030-3030-3030-3030-303030303030")
        def test_05_mocked():
            MOCKED_UUIDS.append("30303030-3030-3030-3030-303030303030")
            result = generate_id()
            results.append(("test_05", str(result), True))
            assert str(result) == "30303030-3030-3030-3030-303030303030"

        def test_06_unmocked():
            result = generate_id()
            results.append(("test_06", str(result), False))
            assert str(result) not in MOCKED_UUIDS

        @freeze_uuid("40404040-4040-4040-4040-404040404040")
        def test_07_mocked():
            MOCKED_UUIDS.append("40404040-4040-4040-4040-404040404040")
            result = generate_id()
            results.append(("test_07", str(result), True))
            assert str(result) == "40404040-4040-4040-4040-404040404040"

        def test_08_unmocked():
            result = generate_id()
            results.append(("test_08", str(result), False))
            assert str(result) not in MOCKED_UUIDS

        @freeze_uuid("50505050-5050-5050-5050-505050505050")
        def test_09_mocked():
            MOCKED_UUIDS.append("50505050-5050-5050-5050-505050505050")
            result = generate_id()
            results.append(("test_09", str(result), True))
            assert str(result) == "50505050-5050-5050-5050-505050505050"

        def test_10_unmocked():
            result = generate_id()
            results.append(("test_10", str(result), False))
            assert str(result) not in MOCKED_UUIDS

        def test_11_final_verify():
            """Verify all results follow the expected pattern."""
            for name, uuid_str, was_mocked in results:
                if was_mocked:
                    assert uuid_str in MOCKED_UUIDS, f"{name} should have mocked UUID"
                else:
                    assert uuid_str not in MOCKED_UUIDS, f"{name} leaked: {uuid_str}"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "11 passed" in result.stdout


# --- Both import patterns in same test ---


@pytest.mark.slow
def test_installed_pkg_both_import_patterns(venv_with_packages, tmp_path):
    """Test both import patterns (direct and module) work together."""
    test_content = textwrap.dedent('''
        """Test both import patterns work correctly."""
        import pytest
        from pytest_uuid import freeze_uuid
        from uuid_testpkg import generate_id  # from uuid import uuid4
        from uuid_testpkg import alt_generate_id  # import uuid

        results = {}

        @freeze_uuid("abababab-abab-abab-abab-abababababab")
        def test_01_both_patterns_mocked():
            """Both patterns should be mocked."""
            from_direct = generate_id()
            from_module = alt_generate_id()

            results["test_01_direct"] = str(from_direct)
            results["test_01_module"] = str(from_module)

            assert str(from_direct) == "abababab-abab-abab-abab-abababababab"
            assert str(from_module) == "abababab-abab-abab-abab-abababababab"

        def test_02_both_patterns_not_mocked():
            """Both patterns should return real UUIDs."""
            from_direct = generate_id()
            from_module = alt_generate_id()

            results["test_02_direct"] = str(from_direct)
            results["test_02_module"] = str(from_module)

            assert str(from_direct) != "abababab-abab-abab-abab-abababababab"
            assert str(from_module) != "abababab-abab-abab-abab-abababababab"
            assert from_direct.version == 4
            assert from_module.version == 4

        def test_03_verify():
            assert results["test_01_direct"] == "abababab-abab-abab-abab-abababababab"
            assert results["test_01_module"] == "abababab-abab-abab-abab-abababababab"
            assert results["test_02_direct"] != "abababab-abab-abab-abab-abababababab"
            assert results["test_02_module"] != "abababab-abab-abab-abab-abababababab"
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_packages, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "3 passed" in result.stdout


# --- Botocore default ignore tests ---


@pytest.fixture
def venv_with_botocore(venv):
    """Create a venv with pytest-uuid and botocore installed."""
    venv.create()

    # Install pytest-uuid from local source (editable)
    venv.install(str(PYTEST_UUID_ROOT), editable=True)

    # Install botocore (lightweight, no need for full boto3)
    venv.install("botocore")

    return venv


@pytest.mark.slow
def test_botocore_ignored_by_default(venv_with_botocore, tmp_path):
    """Test that botocore receives real UUIDs when freeze_uuid is active.

    This verifies the DEFAULT_IGNORE_PACKAGES functionality works correctly
    with a real botocore installation. botocore uses uuid.uuid4() internally
    for generating idempotent ClientTokens in AWS API operations.

    We test this by calling botocore.handlers.generate_idempotent_uuid()
    with a mock model, which triggers botocore's internal uuid.uuid4() call.
    """
    test_content = textwrap.dedent('''
        """Test botocore is ignored by default in freeze_uuid."""
        import uuid
        from pytest_uuid import freeze_uuid

        # Import botocore's internal UUID generator
        from botocore.handlers import generate_idempotent_uuid

        class MockModel:
            """Mock AWS operation model with idempotent member."""
            idempotent_members = ["ClientToken"]

        def test_botocore_gets_real_uuid_when_mocking_active():
            """Verify botocore generates real UUIDs even when freeze_uuid is active."""
            with freeze_uuid("11111111-1111-1111-1111-111111111111"):
                # Direct uuid.uuid4() should return mocked value
                direct_uuid = uuid.uuid4()
                assert str(direct_uuid) == "11111111-1111-1111-1111-111111111111"

                # botocore's generate_idempotent_uuid should get a REAL UUID
                # because botocore is in DEFAULT_IGNORE_PACKAGES
                params = {}
                generate_idempotent_uuid(params, MockModel())

                botocore_uuid = params["ClientToken"]

                # Should NOT be our mocked UUID
                assert botocore_uuid != "11111111-1111-1111-1111-111111111111"

                # Should be a valid v4 UUID
                parsed = uuid.UUID(botocore_uuid)
                assert parsed.version == 4

        def test_botocore_can_be_explicitly_mocked_by_disabling_defaults():
            """Verify botocore CAN be mocked if ignore_defaults is False."""
            with freeze_uuid(
                "22222222-2222-2222-2222-222222222222",
                ignore_defaults=False  # Disable default ignore list
            ):
                params = {}
                generate_idempotent_uuid(params, MockModel())

                botocore_uuid = params["ClientToken"]

                # NOW it should be mocked since we disabled default ignores
                assert botocore_uuid == "22222222-2222-2222-2222-222222222222"

        def test_botocore_ignored_with_decorator():
            """Test @freeze_uuid decorator also respects default ignore list."""
            @freeze_uuid("33333333-3333-3333-3333-333333333333")
            def inner():
                params = {}
                generate_idempotent_uuid(params, MockModel())
                return params["ClientToken"]

            result = inner()

            # Should be a real UUID, not the mocked one
            assert result != "33333333-3333-3333-3333-333333333333"
            assert uuid.UUID(result).version == 4
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_botocore, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "3 passed" in result.stdout


@pytest.mark.slow
def test_botocore_freezer_tracks_real_uuid_calls(venv_with_botocore, tmp_path):
    """Test that freeze_uuid's built-in tracking records botocore's real UUID calls.

    When botocore is ignored, the freezer should still record the call but
    mark it as was_mocked=False and show the caller_module as botocore.

    Note: We use freeze_uuid's built-in tracking instead of spy_uuid because
    they can't be combined (freeze_uuid patches over the spy).
    """
    test_content = textwrap.dedent('''
        """Test freeze_uuid tracking of botocore UUID calls."""
        import uuid
        from pytest_uuid import freeze_uuid

        from botocore.handlers import generate_idempotent_uuid

        class MockModel:
            idempotent_members = ["ClientToken"]

        def test_freezer_tracks_botocore_real_calls():
            """Verify freeze_uuid tracks botocore calls as real (not mocked)."""
            with freeze_uuid("44444444-4444-4444-4444-444444444444") as freezer:
                # First, a direct call (should be mocked)
                direct = uuid.uuid4()
                assert str(direct) == "44444444-4444-4444-4444-444444444444"

                # Then a botocore call (should be real)
                params = {}
                generate_idempotent_uuid(params, MockModel())
                botocore_uuid = params["ClientToken"]

                # Check freezer recorded both calls
                assert freezer.call_count == 2

                # Check the mocked vs real distinction
                mocked_calls = freezer.mocked_calls
                real_calls = freezer.real_calls

                assert len(mocked_calls) == 1
                assert len(real_calls) == 1

                # Mocked call should be our direct uuid.uuid4()
                assert str(mocked_calls[0].uuid) == "44444444-4444-4444-4444-444444444444"

                # Real call should be from botocore
                assert str(real_calls[0].uuid) == botocore_uuid
                assert real_calls[0].caller_module.startswith("botocore")
    ''')

    test_dir = tmp_path / "tests"
    write_test_files(test_dir, test_content)

    result = run_pytest_in_venv(venv_with_botocore, test_dir, "-p", "no:randomly")

    assert result.returncode == 0, (
        f"Tests failed:\\nSTDOUT:\\n{result.stdout}\\nSTDERR:\\n{result.stderr}"
    )
    assert "1 passed" in result.stdout
