"""Idempotent CIE-10 catalog importer (admin payload, §1.5).

Loads the compact ``app/data/cie10_catalog.csv.gz`` artifact into the ``cie10`` table via
``INSERT … ON CONFLICT (code) DO UPDATE``, so re-running never duplicates and always
converges to the file's contents. Runs **after** deploy as an admin Lambda payload
(``{"import_cie10": "dry-run"|"apply"}``) or locally via the CLI — never inside Alembic.

``normalized_description`` is computed here with the shared
:func:`app.core.text_normalization.normalize_clinical_text`, the same function the search
endpoint uses, so the GIN trigram index and the query live in one normalized space (§3).

Modes:

* ``dry-run`` — parse the file and report how many rows *would* be inserted vs updated
  (diffed against the codes already present). No writes.
* ``apply`` — upsert in batches and report the same counts.
"""

import asyncio
import csv
import gzip
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.text_normalization import normalize_clinical_text
from app.db.session import _get_session_factory
from app.models.cie10 import CIE10

_BACKEND_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = _BACKEND_DIR / "app" / "data" / "cie10_catalog.csv.gz"

# Provenance stamped on every row. Bump CATALOG_VERSION when a new source file is shipped;
# diagnoses keep their own ``version_snapshot`` so history is unaffected by a re-version.
CATALOG_VERSION = "CIE-10-MX"
SOURCE = "DGIS-SSA"

_BATCH_SIZE = 1000


def _load_rows() -> list[dict[str, Any]]:
    """Parse the compact gz artifact into cie10 column dicts (normalized in Python)."""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"CIE-10 catalog artifact not found at {CATALOG_PATH}. "
            "Run `python -m scripts.prepare_cie10_catalog` first."
        )
    rows: list[dict[str, Any]] = []
    with gzip.open(CATALOG_PATH, "rt", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            code = (r["code"] or "").strip()
            if not code:
                continue
            description = (r["description"] or "").strip()
            rows.append(
                {
                    "code": code,
                    "description": description,
                    "normalized_description": normalize_clinical_text(description),
                    "chapter_code": r["chapter_code"] or None,
                    "chapter_description": r["chapter_description"] or None,
                    "group_code": r["group_code"] or None,
                    "category_code": r["category_code"] or None,
                    "parent_code": r["parent_code"] or None,
                    "selectable": r["selectable"] == "1",
                    "active": r["active"] == "1",
                    "catalog_version": CATALOG_VERSION,
                    "source": SOURCE,
                }
            )
    return rows


def _envelope(action: str, ok: bool, counts: dict[str, int]) -> dict[str, Any]:
    return {"ok": ok, "action": action, "counts": counts}


async def run_import(mode: str) -> dict[str, Any]:
    """Import (or dry-run) the catalog. Returns an ``ok``/``counts`` envelope."""
    if mode not in ("dry-run", "apply"):
        return _envelope(f"import_cie10:{mode}", False, {})

    rows = _load_rows()
    total = len(rows)
    factory = _get_session_factory()

    async with factory() as session:
        existing = {
            c for (c,) in (await session.execute(select(CIE10.code))).all()
        }
        incoming = {r["code"] for r in rows}
        inserted = len(incoming - existing)
        updated = len(incoming & existing)

        if mode == "dry-run":
            return _envelope(
                "import_cie10:dry-run",
                True,
                {"total": total, "would_insert": inserted, "would_update": updated},
            )

        # apply: upsert in batches, converging every column to the file.
        update_cols = [
            "description",
            "normalized_description",
            "chapter_code",
            "chapter_description",
            "group_code",
            "category_code",
            "parent_code",
            "selectable",
            "active",
            "catalog_version",
            "source",
        ]
        for start in range(0, total, _BATCH_SIZE):
            batch = rows[start : start + _BATCH_SIZE]
            stmt = pg_insert(CIE10).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["code"],
                set_={col: getattr(stmt.excluded, col) for col in update_cols}
                | {"actualizado_en": text("now()")},
            )
            await session.execute(stmt)
        await session.commit()

    return _envelope(
        "import_cie10:apply",
        True,
        {"total": total, "inserted": inserted, "updated": updated},
    )


def run_import_sync(mode: str) -> dict[str, Any]:
    """Sync entry point for the Lambda handler."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_import(mode))


if __name__ == "__main__":
    import json
    import sys

    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    print(json.dumps(run_import_sync(mode_arg), indent=2, default=str))
