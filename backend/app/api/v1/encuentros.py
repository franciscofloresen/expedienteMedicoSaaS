"""API v1 — Encuentros clínicos (atención real, distinta de la agenda).

Fase 2 del ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2 (§5.2/§6.3). Un encuentro modela la
atención que efectivamente ocurrió; la cita solo la agenda. La regla de "una sola
primera vez" la garantiza el índice único parcial en la BD (§3), no este código —
aquí solo sugerimos el tipo y traducimos la violación del índice a un 409 legible.

El vínculo nota↔encuentro se escribe **solo al crear** la nota (create_nota), nunca
como UPDATE a una nota firmada (§1.1).
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.cita import Cita
from app.models.encuentro import EncuentroClinico
from app.models.expediente import Expediente
from app.models.medico import Medico
from app.services.encuentros import (
    TIPOS,
    PrimeraVezDuplicadaError,
    completar_encuentro,
    sugerir_tipo_encuentro,
)

logger = logging.getLogger("medrecord")
router = APIRouter()


class EncuentroCreate(BaseModel):
    expediente_id: UUID
    cita_id: Optional[UUID] = None
    # Optional: if omitted, the server suggests one from the patient's history.
    tipo: Optional[str] = Field(None, max_length=20)


class EncuentroResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    paciente_id: UUID
    expediente_id: UUID
    cita_id: Optional[UUID]
    medico_id: UUID
    tipo: str
    estado: str
    clasificacion_origen: str
    nota_inicial_id: Optional[UUID]
    fecha_inicio: Optional[datetime]
    fecha_fin: Optional[datetime]
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class SugerenciaResponse(BaseModel):
    paciente_id: UUID
    tipo_sugerido: str


async def _get_encuentro_or_404(
    db: AsyncSession, encuentro_id: UUID, tenant_id: UUID
) -> EncuentroClinico:
    stmt = select(EncuentroClinico).where(
        EncuentroClinico.id == encuentro_id,
        EncuentroClinico.tenant_id == tenant_id,
    )
    encuentro = (await db.execute(stmt)).scalar_one_or_none()
    if not encuentro:
        raise HTTPException(status_code=404, detail="Encuentro no encontrado")
    return encuentro


async def _resolve_medico_id(db: AsyncSession, tenant_id: UUID) -> UUID:
    """The active médico for the tenant (one per tenant today, backfilled in Fase 1)."""
    medico_id = (
        await db.execute(
            select(Medico.id)
            .where(Medico.tenant_id == tenant_id, Medico.activo.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()
    if medico_id is None:
        raise HTTPException(
            status_code=409,
            detail="No hay un médico activo para este consultorio.",
        )
    return medico_id


@router.get("/sugerencia", response_model=SugerenciaResponse)
async def sugerir_tipo(
    paciente_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Suggest ``primera_vez``/``subsecuente`` for a patient (suggestion only, §3)."""
    tipo = await sugerir_tipo_encuentro(db, paciente_id)
    return SugerenciaResponse(paciente_id=paciente_id, tipo_sugerido=tipo)


@router.get("/", response_model=List[EncuentroResponse])
async def list_encuentros(
    request: Request,
    paciente_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = UUID(str(request.state.tenant_id))
    stmt = select(EncuentroClinico).where(EncuentroClinico.tenant_id == tenant_id)
    if paciente_id is not None:
        stmt = stmt.where(EncuentroClinico.paciente_id == paciente_id)
    stmt = stmt.order_by(EncuentroClinico.creado_en.desc())
    return (await db.execute(stmt)).scalars().all()


@router.post("/", response_model=EncuentroResponse, status_code=status.HTTP_201_CREATED)
async def create_encuentro(
    data: EncuentroCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = UUID(str(request.state.tenant_id))

    # Expediente must exist and belong to the tenant (RLS-scoped query).
    expediente = (
        await db.execute(
            select(Expediente).where(Expediente.id == data.expediente_id)
        )
    ).scalar_one_or_none()
    if not expediente:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    # Optional cita must belong to the tenant, and a cancelled cita never becomes an
    # encounter (§ Fase 2 correction).
    if data.cita_id is not None:
        cita = (
            await db.execute(select(Cita).where(Cita.id == data.cita_id))
        ).scalar_one_or_none()
        if not cita:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        if cita.estado == "Cancelada":
            raise HTTPException(
                status_code=400,
                detail="Una cita cancelada no puede generar un encuentro.",
            )

    if data.tipo is not None:
        if data.tipo not in TIPOS:
            raise HTTPException(status_code=422, detail="Tipo de encuentro inválido")
        tipo = data.tipo
        origen = "manual"
    else:
        tipo = await sugerir_tipo_encuentro(db, expediente.paciente_id)
        origen = "automatica"

    medico_id = await _resolve_medico_id(db, tenant_id)

    encuentro = EncuentroClinico(
        tenant_id=tenant_id,
        paciente_id=expediente.paciente_id,
        expediente_id=expediente.id,
        cita_id=data.cita_id,
        medico_id=medico_id,
        tipo=tipo,
        estado="programado",
        clasificacion_origen=origen,
        creado_por=tenant_id,
    )
    db.add(encuentro)
    await db.flush()
    await db.refresh(encuentro)
    logger.info(f"Encuentro creado: {encuentro.id} ({tipo}) tenant {tenant_id}")
    return encuentro


@router.post("/{encuentro_id}/iniciar", response_model=EncuentroResponse)
async def iniciar_encuentro(
    encuentro_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = UUID(str(request.state.tenant_id))
    encuentro = await _get_encuentro_or_404(db, encuentro_id, tenant_id)
    if encuentro.estado in ("completado", "cancelado"):
        raise HTTPException(
            status_code=409,
            detail=f"El encuentro ya está {encuentro.estado}.",
        )
    encuentro.estado = "iniciado"
    if encuentro.fecha_inicio is None:
        encuentro.fecha_inicio = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(encuentro)
    return encuentro


@router.post("/{encuentro_id}/completar", response_model=EncuentroResponse)
async def completar(
    encuentro_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = UUID(str(request.state.tenant_id))
    encuentro = await _get_encuentro_or_404(db, encuentro_id, tenant_id)
    if encuentro.estado == "cancelado":
        raise HTTPException(status_code=409, detail="El encuentro está cancelado.")
    try:
        await completar_encuentro(db, encuentro)
    except PrimeraVezDuplicadaError as exc:
        # Structured detail so the frontend can tell this reconcilable conflict (the
        # patient already has a completed primera_vez → offer "complete as subsecuente")
        # apart from the terminal "cancelado" 409 above. ``message`` stays human-readable.
        raise HTTPException(
            status_code=409,
            detail={"code": "primera_vez_duplicada", "message": str(exc)},
        ) from exc
    await db.refresh(encuentro)
    return encuentro


@router.get("/{encuentro_id}", response_model=EncuentroResponse)
async def get_encuentro(
    encuentro_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = UUID(str(request.state.tenant_id))
    return await _get_encuentro_or_404(db, encuentro_id, tenant_id)
