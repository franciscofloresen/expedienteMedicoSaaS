import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_normalization import normalize_clinical_text
from app.db.session import get_db

router = APIRouter()

# A query that starts with a letter followed by a digit (``J06``, ``e11.9``) is treated
# as a code lookup; anything else is a description search.
_CODE_QUERY_RE = re.compile(r"^[A-Za-z]\d")

MIN_QUERY_LEN = 2

_MIN_COMPLETE_CATALOG_ROWS = 10_000


@router.get("")
async def search_cie10(
    q: str,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Search the CIE-10 catalog by code (exact/prefix) or description (trigram).

    Accent- and case-insensitive on the description via the ``pg_trgm`` GIN index over
    ``normalized_description`` (§3); the query is normalized in Python with the same
    :func:`normalize_clinical_text` used at import, so both live in the same space.
    Strict ``limit``/``offset``; only ``active AND selectable`` codes are returned.
    """
    q = (q or "").strip()
    if len(q) < MIN_QUERY_LEN:
        return []

    if _CODE_QUERY_RE.match(q):
        rows = await _search_by_code(db, q, limit, offset)
    else:
        rows = await _search_by_description(db, q, limit, offset)

    if rows:
        return rows

    # Never mask a missing production import with a tiny hard-coded catalog. That made
    # CIE-10 look partially functional while most diagnoses were unavailable. A valid
    # no-match is only returned after confirming the complete catalog is present.
    catalog_rows = (
        await db.execute(text("SELECT count(*) FROM cie10 WHERE active"))
    ).scalar_one()
    if catalog_rows < _MIN_COMPLETE_CATALOG_ROWS:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "cie10_catalog_not_ready",
                "message": (
                    "El catálogo CIE-10 completo todavía no está disponible. "
                    "Ejecuta la importación operativa y vuelve a intentarlo."
                ),
            },
        )
    return []


async def _search_by_code(
    db: AsyncSession, q: str, limit: int, offset: int
) -> list[dict[str, Any]]:
    """Prefix match on the code, matching with or without the dot (``J069``≈``J06.9``)."""
    prefix = q.upper()
    prefix_nodots = prefix.replace(".", "")
    stmt = text(
        """
        SELECT code, description, chapter_description
        FROM cie10
        WHERE active AND selectable
          AND (code ILIKE :prefix || '%' OR replace(code, '.', '') ILIKE :prefix_nd || '%')
        ORDER BY length(code), code
        LIMIT :limit OFFSET :offset
        """
    )
    result = await db.execute(
        stmt,
        {"prefix": prefix, "prefix_nd": prefix_nodots, "limit": limit, "offset": offset},
    )
    return [_row_to_item(r) for r in result]


async def _search_by_description(
    db: AsyncSession, q: str, limit: int, offset: int
) -> list[dict[str, Any]]:
    """Trigram/substring match on the normalized description, ranked by similarity."""
    q_norm = normalize_clinical_text(q)
    if not q_norm:
        return []
    stmt = text(
        """
        SELECT code, description, chapter_description
        FROM cie10
        WHERE active AND selectable
          AND (normalized_description ILIKE '%' || :nq || '%'
               OR normalized_description % :nq)
        ORDER BY similarity(normalized_description, :nq) DESC, length(code), code
        LIMIT :limit OFFSET :offset
        """
    )
    result = await db.execute(
        stmt, {"nq": q_norm, "limit": limit, "offset": offset}
    )
    return [_row_to_item(r) for r in result]


def _row_to_item(row: Any) -> dict[str, Any]:
    return {
        "code": row.code,
        "description": row.description,
        # The UI's ``category`` field shows the chapter name for context.
        "category": row.chapter_description,
    }
