"""API v1 — Fotografías clínicas (Fase 13).

Descriptive metadata over an already-uploaded clinical-file image (the S3 bytes
go through the clinical-file pipeline). Tenant-scoped via RLS. The image is the
delete-protected evidence; this descriptive sidecar is editable.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.fotografia_clinica import FotografiaClinica
from app.schemas.fotografia_clinica import (
    FotografiaCreate,
    FotografiaResponse,
    FotografiaUpdate,
)

logger = logging.getLogger("medrecord.fotografias")
router = APIRouter()


@router.get("/", response_model=List[FotografiaResponse])
async def list_fotografias(
    request: Request,
    paciente_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(FotografiaClinica)
    if paciente_id is not None:
        stmt = stmt.where(FotografiaClinica.paciente_id == paciente_id)
    stmt = stmt.order_by(FotografiaClinica.fecha_toma.desc().nullslast(), FotografiaClinica.creado_en.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/", response_model=FotografiaResponse, status_code=status.HTTP_201_CREATED)
async def create_fotografia(
    payload: FotografiaCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    tenant_id = request.state.tenant_id
    foto = FotografiaClinica(
        tenant_id=tenant_id,
        creado_por=tenant_id,
        **payload.model_dump(),
    )
    db.add(foto)
    await db.flush()
    await db.refresh(foto)
    return foto


@router.put("/{foto_id}", response_model=FotografiaResponse)
async def update_fotografia(
    foto_id: UUID, payload: FotografiaUpdate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    foto = (
        await db.execute(select(FotografiaClinica).where(FotografiaClinica.id == foto_id))
    ).scalar_one_or_none()
    if foto is None:
        raise HTTPException(status_code=404, detail="Fotografía no encontrada")
    for field, value in payload.model_dump().items():
        setattr(foto, field, value)
    foto.modificado_en = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(foto)
    return foto


@router.delete("/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fotografia(
    foto_id: UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> None:
    foto = (
        await db.execute(select(FotografiaClinica).where(FotografiaClinica.id == foto_id))
    ).scalar_one_or_none()
    if foto is None:
        raise HTTPException(status_code=404, detail="Fotografía no encontrada")
    await db.delete(foto)
    await db.flush()
