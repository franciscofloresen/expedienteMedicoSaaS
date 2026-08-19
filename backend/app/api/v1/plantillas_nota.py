"""API v1 — Plantillas de nota configurables (Fase 13).

Doctor-authored note templates: a versioned bundle of field pre-fills that seeds
the note editor. Tenant-scoped via RLS (tenant_id from the JWT only). Editable
preferences, not clinical evidence, so update and hard delete are allowed. Editing
bumps ``version`` so a template change is traceable.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.nota_plantilla import NotaPlantilla
from app.schemas.nota_plantilla import (
    NotaPlantillaCreate,
    NotaPlantillaResponse,
    NotaPlantillaUpdate,
)

logger = logging.getLogger("medrecord.plantillas_nota")
router = APIRouter()


@router.get("/", response_model=List[NotaPlantillaResponse])
async def list_plantillas(request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    """List the tenant's note templates (RLS filtered)."""
    stmt = select(NotaPlantilla).order_by(NotaPlantilla.nombre)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=NotaPlantillaResponse, status_code=status.HTTP_201_CREATED)
async def create_plantilla(
    plantilla_in: NotaPlantillaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = request.state.tenant_id
    plantilla = NotaPlantilla(
        tenant_id=tenant_id,
        creado_por=tenant_id,
        nombre=plantilla_in.nombre,
        campos=plantilla_in.campos.model_dump(exclude_none=True),
    )
    db.add(plantilla)
    await db.flush()
    await db.refresh(plantilla)
    logger.info("Plantilla de nota creada: %s tenant %s", plantilla.id, tenant_id)
    return plantilla


@router.put("/{plantilla_id}", response_model=NotaPlantillaResponse)
async def update_plantilla(
    plantilla_id: UUID,
    plantilla_in: NotaPlantillaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    plantilla = (
        await db.execute(select(NotaPlantilla).where(NotaPlantilla.id == plantilla_id))
    ).scalar_one_or_none()
    if plantilla is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    plantilla.nombre = plantilla_in.nombre
    plantilla.campos = plantilla_in.campos.model_dump(exclude_none=True)
    plantilla.version += 1
    plantilla.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(plantilla)
    return plantilla


@router.delete("/{plantilla_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plantilla(
    plantilla_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    plantilla = (
        await db.execute(select(NotaPlantilla).where(NotaPlantilla.id == plantilla_id))
    ).scalar_one_or_none()
    if plantilla is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    await db.delete(plantilla)
    await db.flush()
