import inspect
import re
import tomllib
from pathlib import Path

from app.main import _ADMIN_PAYLOADS, handler
from scripts.build_lambda_package import (
    AWS_UNPACKED_LIMIT_BYTES,
    CONSTRAINTS_FILE,
    FORBIDDEN_TOP_LEVEL,
    INTERNAL_UNPACKED_BUDGET_BYTES,
    RUNTIME_SCRIPT_FILES,
    prune_package,
    validate_package_layout,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_local_server_is_not_a_production_dependency() -> None:
    config = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    production = [item.lower() for item in config["project"]["dependencies"]]
    development = [item.lower() for item in config["project"]["optional-dependencies"]["dev"]]

    assert not any(item.startswith("uvicorn") for item in production)
    assert any(item.startswith("uvicorn[standard]") for item in development)
    assert "uvicorn" in FORBIDDEN_TOP_LEVEL


def test_every_direct_runtime_dependency_is_constrained() -> None:
    config = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    production_names = {
        re.split(r"[<>=!~;\s\[]", item, maxsplit=1)[0].lower().replace("_", "-")
        for item in config["project"]["dependencies"]
    }
    constrained_names = {
        line.split("==", maxsplit=1)[0].strip().lower().replace("_", "-")
        for line in CONSTRAINTS_FILE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }

    assert production_names <= constrained_names


def test_runtime_script_allowlist_excludes_local_and_destructive_tools() -> None:
    assert "reset_environment.py" not in RUNTIME_SCRIPT_FILES
    assert "smoke_test.py" not in RUNTIME_SCRIPT_FILES
    assert "seed_beta_demo.py" not in RUNTIME_SCRIPT_FILES
    assert "consent_template_tool.py" not in RUNTIME_SCRIPT_FILES


def test_destructive_reset_events_are_not_exposed_by_lambda_handler() -> None:
    # Assert against the dispatch table, not the handler's source text: the table
    # is the whole set of payloads the deployed Lambda will accept, so a new entry
    # cannot slip past this check by living in another function.
    registered = {key for key, _ in _ADMIN_PAYLOADS}
    assert "wipe_all_data" not in registered
    assert "purge_clerk_users" not in registered
    assert not (BACKEND_ROOT / "scripts" / "reset_environment.py").exists()

    # The handler must dispatch only through the table.
    source = inspect.getsource(handler)
    assert "_ADMIN_PAYLOADS" in source


def test_pruning_and_layout_validation(tmp_path: Path) -> None:
    package = tmp_path / "package"
    scripts = package / "scripts"
    scripts.mkdir(parents=True)
    for filename in RUNTIME_SCRIPT_FILES:
        (scripts / filename).write_text("", encoding="utf-8")
    # Despite its name, botocore.docs contains runtime imports used by waiters.
    (package / "botocore" / "docs").mkdir(parents=True)
    (package / "botocore" / "docs" / "index.txt").write_text("runtime", encoding="utf-8")
    (package / "dependency" / "tests").mkdir(parents=True)
    (package / "dependency" / "tests" / "test_x.py").write_text("", encoding="utf-8")
    (package / "dependency" / "__pycache__").mkdir()
    (package / "dependency" / "__pycache__" / "x.pyc").write_bytes(b"cache")

    prune_package(package)
    validate_package_layout(package)

    assert (package / "botocore" / "docs" / "index.txt").exists()
    assert not (package / "dependency" / "tests").exists()
    assert not (package / "dependency" / "__pycache__").exists()


def test_internal_budget_keeps_headroom_below_aws_limit() -> None:
    assert INTERNAL_UNPACKED_BUDGET_BYTES == 225 * 1024 * 1024
    assert INTERNAL_UNPACKED_BUDGET_BYTES < AWS_UNPACKED_LIMIT_BYTES
