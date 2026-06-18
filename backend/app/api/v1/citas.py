import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.cita import Cita
from app.schemas.cita import CitaCreate, CitaResponse, CitaUpdate

logger = logging.getLogger("medrecord")
router = APIRouter()

@router.get("/", response_model=List[CitaResponse])
async def read_citas(
    request: Request,
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(Cita)
    if start_date:
        stmt = stmt.where(Cita.fecha_inicio >= start_date)
    if end_date:
        stmt = stmt.where(Cita.fecha_inicio <= end_date)

    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/", response_model=CitaResponse, status_code=status.HTTP_201_CREATED)
async def create_cita(
    cita_in: CitaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = request.state.tenant_id
    cita = Cita(
        tenant_id=tenant_id,
        **cita_in.model_dump()
    )
    db.add(cita)
    await db.flush()
    await db.refresh(cita)

    logger.info(f"Cita creada: {cita.id} para tenant {tenant_id}")
    return cita

@router.put("/{cita_id}", response_model=CitaResponse)
async def update_cita(
    cita_id: UUID,
    cita_in: CitaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(Cita).where(Cita.id == cita_id)
    result = await db.execute(stmt)
    cita = result.scalar_one_or_none()

    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    update_data = cita_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cita, field, value)

    cita.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(cita)

    logger.info(f"Cita actualizada: {cita.id}")
    return cita

@router.delete("/{cita_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cita(
    cita_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(Cita).where(Cita.id == cita_id)
    result = await db.execute(stmt)
    cita = result.scalar_one_or_none()

    if not cita:
        raise HTTPException(status_code=404, detail="Cita no encontrada")

    await db.delete(cita)
    await db.flush()
    logger.info(f"Cita eliminada: {cita_id}")
