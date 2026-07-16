"""Build and verify the minimal production Lambda ZIP.

The default dependency set in ``pyproject.toml`` is the Lambda runtime. Developer
tools belong in the ``dev`` extra and must never leak into this artifact. Only scripts
invoked by ``app.main.handler`` are copied; local catalog, seed, smoke and destructive
utilities are deliberately excluded.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS_FILE = BACKEND_ROOT / "lambda-constraints.txt"
DEFAULT_TEMP_DIR = Path(tempfile.gettempdir())

RUNTIME_SCRIPT_FILES = (
    "__init__.py",
    "extract_legacy_diagnosticos.py",
    "import_cie10.py",
    "import_consent_templates.py",
    "release_cedula.py",
    "upgrade_tenant.py",
    "verify_file_storage.py",
    "verify_registry.py",
)

# These packages are useful only for the local ASGI server. Their presence means a
# dev extra accidentally leaked into the production artifact.
FORBIDDEN_TOP_LEVEL = (
    "httptools",
    "uvicorn",
    "uvloop",
    "watchfiles",
    "websockets",
    "yaml",
)

REQUIRED_MODULES = (
    "alembic",
    "app.main",
    "asyncpg",
    "boto3",
    "cryptography",
    "fastapi",
    "httpx",
    "jwt",
    "mangum",
    "PIL",
    "pydantic",
    "pydantic_settings",
    "pythonjsonlogger",
    "reportlab",
    "scripts.extract_legacy_diagnosticos",
    "scripts.import_cie10",
    "scripts.import_consent_templates",
    "scripts.release_cedula",
    "scripts.upgrade_tenant",
    "scripts.verify_file_storage",
    "scripts.verify_registry",
    "sqlalchemy",
    "tenacity",
)

DIRECT_UPLOAD_WARNING_BYTES = 45 * 1024 * 1024
INTERNAL_UNPACKED_BUDGET_BYTES = 225 * 1024 * 1024
AWS_UNPACKED_LIMIT_BYTES = 250 * 1024 * 1024


def _copy_runtime_source(package_dir: Path) -> None:
    for directory in ("app", "alembic"):
        shutil.copytree(
            BACKEND_ROOT / directory,
            package_dir / directory,
            dirs_exist_ok=True,
        )
    shutil.copy2(BACKEND_ROOT / "alembic.ini", package_dir / "alembic.ini")

    packaged_scripts = package_dir / "scripts"
    if packaged_scripts.exists():
        shutil.rmtree(packaged_scripts)
    packaged_scripts.mkdir()
    for filename in RUNTIME_SCRIPT_FILES:
        shutil.copy2(BACKEND_ROOT / "scripts" / filename, packaged_scripts / filename)


def prune_package(package_dir: Path) -> None:
    """Remove build/dev material that no production import can require."""
    removable_directories: list[Path] = []
    for path in package_dir.rglob("*"):
        if not path.is_dir():
            continue
        if path.name == "__pycache__":
            removable_directories.append(path)
        elif path.name in {"test", "tests"} and not path.is_relative_to(package_dir / "app"):
            removable_directories.append(path)

    for path in sorted(
        set(removable_directories),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if path.exists():
            shutil.rmtree(path)

    for pattern in ("*.pyc", "*.pyo"):
        for path in package_dir.rglob(pattern):
            path.unlink()

    # Console entry points are never executed by Lambda.
    bin_dir = package_dir / "bin"
    if bin_dir.exists():
        shutil.rmtree(bin_dir)


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def validate_package_layout(package_dir: Path) -> None:
    missing_scripts = [
        name for name in RUNTIME_SCRIPT_FILES if not (package_dir / "scripts" / name).is_file()
    ]
    if missing_scripts:
        raise RuntimeError(f"Missing production scripts: {missing_scripts}")

    leaked = [name for name in FORBIDDEN_TOP_LEVEL if (package_dir / name).exists()]
    if leaked:
        raise RuntimeError(f"Developer-only packages leaked into Lambda: {leaked}")

    forbidden_script = package_dir / "scripts" / "reset_environment.py"
    if forbidden_script.exists():
        raise RuntimeError("Destructive reset operations must never ship to production")


def verify_runtime_imports(package_dir: Path) -> None:
    """Import through the packaged sys.path, not the developer virtualenv."""
    required_modules_json = json.dumps(REQUIRED_MODULES)
    script = f"""
import importlib
import importlib.util
import json
import sys

package_dir = {str(package_dir)!r}
sys.path = [package_dir] + [
    path for path in sys.path
    if path and 'site-packages' not in path and path != {str(BACKEND_ROOT)!r}
]
modules = json.loads({required_modules_json!r})
missing = [name for name in modules if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit(f'Missing runtime modules: {{missing}}')
for name in modules:
    importlib.import_module(name)
"""
    env = {
        **os.environ,
        "ENVIRONMENT": "testing",
        "JWT_DEV_SECRET": "package-verification-secret-at-least-32-chars",
        "CLERK_SECRET_KEY": "sk_test_package_verification",
    }
    subprocess.run(  # noqa: S603 - fixed interpreter and generated audit script
        [sys.executable, "-c", script],
        check=True,
        cwd=package_dir,
        env=env,
    )


def _write_zip(package_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(package_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(package_dir))


def _top_level_sizes(package_dir: Path) -> list[dict[str, int | str]]:
    rows = [
        {
            "path": path.name,
            "bytes": _directory_size(path) if path.is_dir() else path.stat().st_size,
        }
        for path in package_dir.iterdir()
    ]
    return sorted(rows, key=lambda row: int(row["bytes"]), reverse=True)[:20]


def build_package(package_dir: Path, zip_path: Path, manifest_path: Path) -> dict[str, Any]:
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    subprocess.run(  # noqa: S603 - fixed interpreter and argument vector
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-compile",
            "--constraint",
            str(CONSTRAINTS_FILE),
            "--target",
            str(package_dir),
            ".",
        ],
        check=True,
        cwd=BACKEND_ROOT,
    )
    _copy_runtime_source(package_dir)
    prune_package(package_dir)
    validate_package_layout(package_dir)
    verify_runtime_imports(package_dir)
    _write_zip(package_dir, zip_path)

    unpacked_bytes = _directory_size(package_dir)
    zip_bytes = zip_path.stat().st_size
    manifest: dict[str, Any] = {
        "zip_bytes": zip_bytes,
        "unpacked_bytes": unpacked_bytes,
        "direct_upload_warning": zip_bytes > DIRECT_UPLOAD_WARNING_BYTES,
        "internal_unpacked_budget_bytes": INTERNAL_UNPACKED_BUDGET_BYTES,
        "aws_unpacked_limit_bytes": AWS_UNPACKED_LIMIT_BYTES,
        "runtime_scripts": list(RUNTIME_SCRIPT_FILES),
        "forbidden_packages_absent": list(FORBIDDEN_TOP_LEVEL),
        "top_level": _top_level_sizes(package_dir),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if unpacked_bytes > INTERNAL_UNPACKED_BUDGET_BYTES:
        raise RuntimeError(
            f"Lambda package is {unpacked_bytes} bytes unzipped; internal budget is "
            f"{INTERNAL_UNPACKED_BUDGET_BYTES} bytes"
        )
    if unpacked_bytes > AWS_UNPACKED_LIMIT_BYTES:
        raise RuntimeError("Lambda package exceeds AWS's 250 MiB unzipped hard limit")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-dir",
        type=Path,
        default=DEFAULT_TEMP_DIR / "lambda-package",
    )
    parser.add_argument(
        "--zip-path",
        type=Path,
        default=DEFAULT_TEMP_DIR / "backend.zip",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=DEFAULT_TEMP_DIR / "lambda-package-manifest.json",
    )
    args = parser.parse_args()
    manifest = build_package(args.package_dir, args.zip_path, args.manifest_path)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
