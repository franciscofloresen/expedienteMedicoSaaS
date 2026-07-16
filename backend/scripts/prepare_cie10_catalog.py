"""Offline prep: compact the raw DGIS/SSA CIE-10 CSV into the shipped catalog artifact.

Run **once, locally** (not in the Lambda) whenever the source catalog changes. It reads
the raw 76-column ``catalogo_cie10.csv`` and writes a small, gzipped
``backend/app/data/cie10_catalog.csv.gz`` with only the ~9 columns the importer needs.
Keeping the 5.6 MB raw file out of git and shipping a compact artifact keeps the Lambda
package small (cheap) and the import fast.

Transformations (see ROADMAP §5.3 / plan "Data model decisions"):

* ``CATALOG_KEY`` → dotted ``code``: 3-char stays (``A00``); 4-char gets a dot after the
  3rd char (``A000`` → ``A00.0``), matching the clinical/display convention.
* ``category_code`` = first 3 chars; ``parent_code`` = the category for 4-char codes, else
  empty.
* ``active`` / ``selectable`` = (``VALID == 'SI'``).

``normalized_description`` is NOT precomputed here — the importer computes it with
``app.core.text_normalization.normalize_clinical_text`` so there is a single source of
truth shared with the search endpoint.

Usage::

    python -m scripts.prepare_cie10_catalog [RAW_CSV_PATH]
    # default RAW_CSV_PATH = <repo-root>/catalogo_cie10.csv
"""

import csv
import gzip
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent
_DEFAULT_RAW = _REPO_ROOT / "catalogo_cie10.csv"
OUTPUT_PATH = _BACKEND_DIR / "app" / "data" / "cie10_catalog.csv.gz"

# Compact artifact columns (order matters — the importer reads by header).
OUTPUT_FIELDS = [
    "code",
    "description",
    "chapter_code",
    "chapter_description",
    "group_code",
    "category_code",
    "parent_code",
    "selectable",
    "active",
]


def to_dotted_code(catalog_key: str) -> str:
    """Canonicalize a DGIS ``CATALOG_KEY`` into the standard clinical code.

    * ``A000`` → ``A00.0`` (real subdivision: dot after the 3rd char).
    * ``I10X`` → ``I10`` (``X`` is the DGIS placeholder for "no subdivision"; the
      codeable rubric is the 3-char category, which is what clinicians and legacy notes
      write).
    * 3-char keys are returned unchanged.
    """
    key = catalog_key.strip().upper()
    if len(key) <= 3:
        return key
    if key[3] == "X":  # placeholder 4th character → canonical 3-char code
        return key[:3]
    return f"{key[:3]}.{key[3:]}"


def transform_row(row: dict[str, str]) -> dict[str, str] | None:
    raw_key = (row.get("CATALOG_KEY") or "").strip()
    if not raw_key:
        return None
    code = to_dotted_code(raw_key)
    category_code = raw_key[:3].upper()
    # A code with a dot is a genuine subdivision → its parent is the category; a bare
    # 3-char code (incl. an X-placeholder collapsed to 3 chars) is itself the category.
    parent_code = category_code if "." in code else ""
    is_valid = (row.get("VALID") or "").strip().upper() == "SI"
    return {
        "code": code,
        "description": (row.get("NOMBRE") or "").strip(),
        "chapter_code": (row.get("CLAVE_CAPITULO") or "").strip(),
        "chapter_description": (row.get("CAPITULO") or "").strip(),
        "group_code": (row.get("GRUPO1") or "").strip(),
        "category_code": category_code,
        "parent_code": parent_code,
        "selectable": "1" if is_valid else "0",
        "active": "1" if is_valid else "0",
    }


def main() -> int:
    raw_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_RAW
    if not raw_path.exists():
        print(f"ERROR: raw catalog not found at {raw_path}", file=sys.stderr)
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Collapsing the X-placeholder can collide a 3-char row with its X-filler sibling
    # (e.g. U92 + U92X). Keep one row per code, preferring the selectable/valid one so a
    # non-selectable 3-char header never shadows the codeable rubric.
    by_code: dict[str, dict[str, str]] = {}
    for row in csv.DictReader(open(raw_path, encoding="utf-8", newline="")):
        out = transform_row(row)
        if out is None:
            continue
        prev = by_code.get(out["code"])
        if prev is None or (out["selectable"] == "1" and prev["selectable"] == "0"):
            by_code[out["code"]] = out

    with gzip.open(OUTPUT_PATH, "wt", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for out in by_code.values():
            writer.writerow(out)

    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"Wrote {len(by_code)} codes to {OUTPUT_PATH} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
