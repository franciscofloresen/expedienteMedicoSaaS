"""API v1 — Expedientes Clínicos (NOM-004 §5.4)."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.services.encryption import decrypt_field, encrypt_field

router = APIRouter()


class ExpedienteCreate(BaseModel):
    paciente_id: UUID
    numero_expediente: str | None = None
    antecedentes: str | None = Field(
        None, description="Antecedentes heredofamiliares, personales patológicos, etc."
    )


class ExpedienteUpdate(BaseModel):
    antecedentes: str


@router.get("/")
async def list_expedientes(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List all expedientes with basic patient info."""
    stmt = (
        select(Expediente, Paciente)
        .join(Paciente, Expediente.paciente_id == Paciente.id)
        .order_by(desc(Expediente.creado_en))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": str(exp.id),
            "folio": exp.folio,
            "paciente_id": str(exp.paciente_id),
            "paciente_nombre": pac.nombre_completo,
            "paciente_curp": pac.curp,
            "creado_en": exp.creado_en.isoformat() if exp.creado_en else None,
        }
        for exp, pac in rows
    ]


@router.post("/", status_code=201)
async def create_expediente(
    data: ExpedienteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = request.state.tenant_id

    # Verify patient exists and belongs to tenant
    stmt_paciente = select(Paciente).where(Paciente.id == data.paciente_id)
    result = await db.execute(stmt_paciente)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Enforce plan limits
    plan = getattr(request.state, "plan", "basico")
    if plan == "basico":
        from sqlalchemy import func

        stmt_count = select(func.count(Expediente.id))
        count = (await db.execute(stmt_count)).scalar_one()
        if count >= 5:
            raise HTTPException(
                status_code=403,
                detail="Límite alcanzado: El plan Básico permite un máximo de 5 expedientes. Por favor contacte soporte (franciscofloresenr@gmail.com o WhatsApp +523121940941) para activar su cuenta Pro.",
            )

    # Check if expediente already exists
    stmt_exp = select(Expediente).where(Expediente.paciente_id == data.paciente_id)
    result = await db.execute(stmt_exp)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="El paciente ya tiene un expediente activo"
        )

    antecedentes_cifrado = None
    if data.antecedentes:
        antecedentes_cifrado = encrypt_field(data.antecedentes, tenant_id)

    expediente = Expediente(
        tenant_id=tenant_id,
        paciente_id=data.paciente_id,
        folio=data.numero_expediente or f"EXP-{str(data.paciente_id)[:8].upper()}",
        antecedentes_cifrado=antecedentes_cifrado,
        creado_por=tenant_id,
    )
    db.add(expediente)
    await db.flush()

    return {"id": str(expediente.id), "numero_expediente": expediente.folio}


@router.get("/paciente/{paciente_id}")
async def get_expediente_by_paciente(
    paciente_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = select(Expediente).where(Expediente.paciente_id == paciente_id)
    expediente = (await db.execute(stmt)).scalar_one_or_none()

    if not expediente:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    antecedentes = None
    if expediente.antecedentes_cifrado:
        tenant_id = request.state.tenant_id
        antecedentes = decrypt_field(expediente.antecedentes_cifrado, tenant_id)

    return {
        "id": str(expediente.id),
        "paciente_id": str(expediente.paciente_id),
        "numero_expediente": expediente.folio,
        "antecedentes": antecedentes,
        "creado_en": expediente.creado_en.isoformat(),
    }


@router.put("/{expediente_id}/antecedentes")
async def update_antecedentes(
    expediente_id: UUID,
    data: ExpedienteUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = request.state.tenant_id

    stmt = select(Expediente).where(Expediente.id == expediente_id)
    expediente = (await db.execute(stmt)).scalar_one_or_none()

    if not expediente:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    if data.antecedentes is not None:
        expediente.antecedentes_cifrado = encrypt_field(data.antecedentes, tenant_id)

    await db.flush()
    return {"status": "success"}
