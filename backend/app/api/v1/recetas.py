import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.receta import Receta

router = APIRouter()

class RecetaCreate(BaseModel):
    nota_id: str
    medicamentos: list[dict[str, Any]]
    indicaciones_generales: str | None = None

@router.post("")
async def create_receta(
    data: RecetaCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    tenant_id = request.state.tenant_id

    receta = Receta(
        tenant_id=uuid.UUID(tenant_id),
        nota_id=uuid.UUID(data.nota_id),
        medicamentos=data.medicamentos,
        indicaciones_generales=data.indicaciones_generales
    )
    db.add(receta)
    await db.commit()
    await db.refresh(receta)

    return {
        "id": str(receta.id),
        "nota_id": str(receta.nota_id),
        "medicamentos": receta.medicamentos,
        "indicaciones_generales": receta.indicaciones_generales,
        "creado_en": receta.creado_en.isoformat()
    }

@router.get("/{id}")
async def get_receta(id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    tenant_id = request.state.tenant_id
    stmt = select(Receta).where(Receta.id == uuid.UUID(id), Receta.tenant_id == uuid.UUID(tenant_id))
    result = await db.execute(stmt)
    receta = result.scalar_one_or_none()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return {
        "id": str(receta.id),
        "nota_id": str(receta.nota_id),
        "medicamentos": receta.medicamentos,
        "indicaciones_generales": receta.indicaciones_generales,
        "creado_en": receta.creado_en.isoformat()
    }
