import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.cita import Cita
from app.models.tenant import Tenant
from app.schemas.cita import CitaCreate, CitaResponse, CitaUpdate
from app.services.email import queue_cita_notification

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
    cita = Cita(tenant_id=tenant_id, **cita_in.model_dump())
    db.add(cita)
    await db.flush()
    await db.refresh(cita)

    logger.info(f"Cita creada: {cita.id} para tenant {tenant_id}")

    tenant = await db.get(Tenant, tenant_id)
    if tenant:
        to = tenant.notification_email or tenant.email
        queue_cita_notification(db, to, tenant.nombre_medico, cita, "creada")
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
    # No-op update: nothing changed → no state transition, no email.
    if not update_data:
        return cita

    was_cancelada = cita.estado == "Cancelada"
    for field, value in update_data.items():
        setattr(cita, field, value)

    cita.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(cita)

    logger.info(f"Cita actualizada: {cita.id}")

    # One mail per real action: "cancelada" only on the transition into
    # Cancelada, otherwise "actualizada". Re-PUTs that keep the same state
    # don't re-fire the cancel mail.
    now_cancelada = cita.estado == "Cancelada"
    action = "cancelada" if (now_cancelada and not was_cancelada) else "actualizada"
    tenant = await db.get(Tenant, cita.tenant_id)
    if tenant:
        to = tenant.notification_email or tenant.email
        queue_cita_notification(db, to, tenant.nombre_medico, cita, action)
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

    # Snapshot for the notification while the row is still loaded; the mail is
    # sent only after the delete commits. DELETE is the UI's cancel action, so
    # it maps to "cancelada".
    tenant = await db.get(Tenant, cita.tenant_id)
    if tenant:
        to = tenant.notification_email or tenant.email
        queue_cita_notification(db, to, tenant.nombre_medico, cita, "cancelada")

    await db.delete(cita)
    await db.flush()
    logger.info(f"Cita eliminada: {cita_id}")
