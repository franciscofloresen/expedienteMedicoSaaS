"""Best-effort extraction of legacy free-text diagnoses into ``nota_diagnosticos``.

Fase 3 (roadmap §7.3): older notes store a single free-text ``notas.diagnostico_cie10``
(e.g. ``"J06.9 - Infección aguda…"`` or just ``"E11.9"``). This admin payload parses a
leading CIE-10 code out of that text, matches it to the imported catalog, and writes a
structured ``nota_diagnosticos`` row **pointing at the note**.

Regla de oro (§1.1): the note is **never UPDATEd** — a signed note is immutable, so we
only INSERT the child row. The original free text stays in ``notas.diagnostico_cie10`` as
evidence. Extraction is *best-effort and declared as such* (§3): no promise of a complete
mapping; unmatched notes are simply reported.

Idempotent: a note that already has any ``nota_diagnosticos`` row is skipped, so re-running
never duplicates. Runs on the admin (RLS-bypassing) connection and sets ``tenant_id``
explicitly from each note.

Modes ``dry-run`` / ``apply``; both return the same counts envelope.
"""

import asyncio
import re
from typing import Any

from sqlalchemy import text

from app.db.session import _get_session_factory

# Leading CIE-10 token: a letter, two digits, optionally a dot + one more digit.
_CODE_RE = re.compile(r"([A-Za-z]\d{2})\.?(\d)?")


def parse_code(free_text: str | None) -> str | None:
    """Extract and dot-normalize a CIE-10 code from free text, or return ``None``."""
    if not free_text:
        return None
    m = _CODE_RE.search(free_text)
    if not m:
        return None
    base, sub = m.group(1).upper(), m.group(2)
    return f"{base}.{sub}" if sub else base


def _envelope(action: str, ok: bool, counts: dict[str, int]) -> dict[str, Any]:
    return {"ok": ok, "action": action, "counts": counts}


async def run_extraction(mode: str) -> dict[str, Any]:
    if mode not in ("dry-run", "apply"):
        return _envelope(f"extract_legacy_diagnosticos:{mode}", False, {})

    factory = _get_session_factory()
    scanned = matched = unmatched = inserted = 0

    async with factory() as session:
        # Notes with legacy free text and no structured diagnosis yet. Admin connection
        # bypasses RLS, so this spans all tenants; tenant_id comes from each note.
        rows = (
            await session.execute(
                text(
                    """
                    SELECT n.id, n.tenant_id, n.diagnostico_cie10, n.creado_por
                    FROM notas n
                    WHERE n.diagnostico_cie10 IS NOT NULL
                      AND n.diagnostico_cie10 <> ''
                      AND NOT EXISTS (
                          SELECT 1 FROM nota_diagnosticos d WHERE d.nota_id = n.id
                      )
                    """
                )
            )
        ).all()

        for nota_id, tenant_id, legacy, creado_por in rows:
            scanned += 1
            code = parse_code(legacy)
            if code is None:
                unmatched += 1
                continue
            # Match the parsed code against the catalog: exact dotted first, then the
            # 3-char category as a fallback (a bare "J069" → J06.9 already dotted above).
            catalog = (
                await session.execute(
                    text(
                        """
                        SELECT code, description, catalog_version FROM cie10
                        WHERE code = :code OR code = :base
                        ORDER BY (code = :code) DESC, length(code) DESC
                        LIMIT 1
                        """
                    ),
                    {"code": code, "base": code[:3]},
                )
            ).first()
            if catalog is None:
                unmatched += 1
                continue

            matched += 1
            if mode == "dry-run":
                continue

            await session.execute(
                text(
                    """
                    INSERT INTO nota_diagnosticos
                        (tenant_id, nota_id, cie10_code, orden, es_principal, certeza,
                         descripcion_snapshot, version_snapshot, creado_por)
                    VALUES
                        (:tenant_id, :nota_id, :code, 0, true, 'presuntivo',
                         :descripcion, :version, :creado_por)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "nota_id": nota_id,
                    "code": catalog.code,
                    "descripcion": catalog.description,
                    "version": catalog.catalog_version,
                    "creado_por": creado_por,
                },
            )
            inserted += 1

        if mode == "apply":
            await session.commit()

    return _envelope(
        f"extract_legacy_diagnosticos:{mode}",
        True,
        {
            "scanned": scanned,
            "matched": matched,
            "unmatched": unmatched,
            "inserted": inserted,
        },
    )


def run_extraction_sync(mode: str) -> dict[str, Any]:
    """Sync entry point for the Lambda handler."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(run_extraction(mode))


if __name__ == "__main__":
    import json
    import sys

    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "dry-run"
    print(json.dumps(run_extraction_sync(mode_arg), indent=2, default=str))
