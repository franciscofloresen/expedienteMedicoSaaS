import re
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.text_normalization import normalize_clinical_text
from app.db.session import get_db

router = APIRouter()

# A query that starts with a letter followed by a digit (``J06``, ``e11.9``) is treated
# as a code lookup; anything else is a description search.
_CODE_QUERY_RE = re.compile(r"^[A-Za-z]\d")

MIN_QUERY_LEN = 2

# Beta safety net: if the catalog table has not been imported yet in an environment,
# fall back to a tiny static list so the note editor is never empty. Once the ~14.5k-row
# catalog is loaded (Fase 3 importer), real rows always win and this is never reached.
_STATIC_FALLBACK = [
    {"code": "J00", "description": "Rinofaringitis aguda (resfriado común)", "category": "Respiratorio"},
    {"code": "J06.9", "description": "Infección aguda de las vías respiratorias superiores, no especificada", "category": "Respiratorio"},
    {"code": "E11.9", "description": "Diabetes mellitus tipo 2 sin complicaciones", "category": "Endocrino"},
    {"code": "I10", "description": "Hipertensión esencial (primaria)", "category": "Cardiovascular"},
    {"code": "A09", "description": "Diarrea y gastroenteritis de presunto origen infeccioso", "category": "Gastrointestinal"},
    {"code": "N39.0", "description": "Infección de vías urinarias, sitio no especificado", "category": "Genitourinario"},
]


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

    # Unseeded environment (or a non-matching code): fall back to the static list, only
    # ever on the first page so pagination never loops on it.
    if offset == 0:
        q_norm = normalize_clinical_text(q)
        return [
            item
            for item in _STATIC_FALLBACK
            if q.lower() in item["code"].lower()
            or q_norm in normalize_clinical_text(item["description"])
        ]
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
