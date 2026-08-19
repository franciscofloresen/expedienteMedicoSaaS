"""API v1 — Procedimientos: checklists pre/post y eventos adversos (Fase 13).

Tenant-scoped via RLS (tenant_id from the JWT only). Working clinical-workflow
records the doctor edits over time — update and hard delete are allowed.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.procedimiento import EventoAdverso, ProcedimientoChecklist
from app.schemas.procedimiento import (
    ChecklistCreate,
    ChecklistResponse,
    ChecklistUpdate,
    EventoAdversoCreate,
    EventoAdversoResponse,
    EventoAdversoUpdate,
)

logger = logging.getLogger("medrecord.procedimientos")
router = APIRouter()


# ── Checklists ──
@router.get("/checklists", response_model=List[ChecklistResponse])
async def list_checklists(
    request: Request,
    paciente_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(ProcedimientoChecklist)
    if paciente_id is not None:
        stmt = stmt.where(ProcedimientoChecklist.paciente_id == paciente_id)
    stmt = stmt.order_by(ProcedimientoChecklist.creado_en.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/checklists", response_model=ChecklistResponse, status_code=status.HTTP_201_CREATED)
async def create_checklist(
    payload: ChecklistCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    tenant_id = request.state.tenant_id
    checklist = ProcedimientoChecklist(
        tenant_id=tenant_id,
        creado_por=tenant_id,
        paciente_id=payload.paciente_id,
        encuentro_id=payload.encuentro_id,
        momento=payload.momento,
        items=[i.model_dump() for i in payload.items],
        observaciones=payload.observaciones,
    )
    db.add(checklist)
    await db.flush()
    await db.refresh(checklist)
    return checklist


@router.put("/checklists/{checklist_id}", response_model=ChecklistResponse)
async def update_checklist(
    checklist_id: UUID, payload: ChecklistUpdate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    checklist = (
        await db.execute(
            select(ProcedimientoChecklist).where(ProcedimientoChecklist.id == checklist_id)
        )
    ).scalar_one_or_none()
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist no encontrado")
    checklist.items = [i.model_dump() for i in payload.items]
    checklist.observaciones = payload.observaciones
    checklist.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(checklist)
    return checklist


@router.delete("/checklists/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_checklist(
    checklist_id: UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    checklist = (
        await db.execute(
            select(ProcedimientoChecklist).where(ProcedimientoChecklist.id == checklist_id)
        )
    ).scalar_one_or_none()
    if checklist is None:
        raise HTTPException(status_code=404, detail="Checklist no encontrado")
    await db.delete(checklist)
    await db.flush()


# ── Adverse events ──
@router.get("/eventos-adversos", response_model=List[EventoAdversoResponse])
async def list_eventos(
    request: Request,
    paciente_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(EventoAdverso)
    if paciente_id is not None:
        stmt = stmt.where(EventoAdverso.paciente_id == paciente_id)
    stmt = stmt.order_by(EventoAdverso.creado_en.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post(
    "/eventos-adversos", response_model=EventoAdversoResponse, status_code=status.HTTP_201_CREATED
)
async def create_evento(
    payload: EventoAdversoCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    tenant_id = request.state.tenant_id
    evento = EventoAdverso(
        tenant_id=tenant_id,
        creado_por=tenant_id,
        paciente_id=payload.paciente_id,
        encuentro_id=payload.encuentro_id,
        descripcion=payload.descripcion,
        severidad=payload.severidad,
        fecha=payload.fecha,
        manejo=payload.manejo,
    )
    db.add(evento)
    await db.flush()
    await db.refresh(evento)
    return evento


@router.put("/eventos-adversos/{evento_id}", response_model=EventoAdversoResponse)
async def update_evento(
    evento_id: UUID, payload: EventoAdversoUpdate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    evento = (
        await db.execute(select(EventoAdverso).where(EventoAdverso.id == evento_id))
    ).scalar_one_or_none()
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento adverso no encontrado")
    evento.descripcion = payload.descripcion
    evento.severidad = payload.severidad
    evento.fecha = payload.fecha
    evento.manejo = payload.manejo
    evento.estado = payload.estado
    evento.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(evento)
    return evento


@router.delete("/eventos-adversos/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evento(
    evento_id: UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    evento = (
        await db.execute(select(EventoAdverso).where(EventoAdverso.id == evento_id))
    ).scalar_one_or_none()
    if evento is None:
        raise HTTPException(status_code=404, detail="Evento adverso no encontrado")
    await db.delete(evento)
    await db.flush()
