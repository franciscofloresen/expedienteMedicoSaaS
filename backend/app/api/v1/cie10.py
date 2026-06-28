from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.cie10 import CIE10

router = APIRouter()

@router.get("")
async def search_cie10(q: str, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Search CIE-10 codes by code or description (top 500 for beta).
    Ponytail: simple ILIKE search, no Elasticsearch needed.
    """
    if not q or len(q) < 2:
        return []

    stmt = (
        select(CIE10)
        .where(
            CIE10.description.ilike(f"%{q}%") | CIE10.code.ilike(f"%{q}%")
        )
        .limit(10)
    )
    results = await db.execute(stmt)
    items = results.scalars().all()

    # Ponytail: Fallback to static list for Beta if DB is unseeded in prod
    if not items:
        top_cie10 = [
            {"code": "J00", "description": "Rinofaringitis aguda (resfriado común)", "category": "Respiratorio"},
            {"code": "J06.9", "description": "Infección aguda de las vías respiratorias superiores, no especificada", "category": "Respiratorio"},
            {"code": "E11.9", "description": "Diabetes mellitus tipo 2 sin complicaciones", "category": "Endocrino"},
            {"code": "I10", "description": "Hipertensión esencial (primaria)", "category": "Cardiovascular"},
            {"code": "A09", "description": "Diarrea y gastroenteritis de presunto origen infeccioso", "category": "Gastrointestinal"},
            {"code": "N39.0", "description": "Infección de vías urinarias, sitio no especificado", "category": "Genitourinario"},
        ]
        q_lower = q.lower()
        return [
            item for item in top_cie10
            if q_lower in item["code"].lower() or q_lower in item["description"].lower()
        ]

    return [
        {"code": i.code, "description": i.description, "category": i.category}
        for i in items
    ]
