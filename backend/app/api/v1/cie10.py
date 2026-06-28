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

    return [
        {"code": i.code, "description": i.description, "category": i.category}
        for i in items
    ]
