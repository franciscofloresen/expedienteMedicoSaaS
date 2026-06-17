"""API v1 — Expedientes Clínicos (NOM-004 §5.4)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.models.tenant_key import TenantKey
from app.services.encryption import encrypt_field, decrypt_field

router = APIRouter()

class ExpedienteCreate(BaseModel):
    paciente_id: str
    numero_expediente: str | None = None
    antecedentes: str | None = Field(None, description="Antecedentes heredofamiliares, personales patológicos, etc.")

class ExpedienteUpdate(BaseModel):
    antecedentes: str

@router.get("/")
async def list_expedientes(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
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
):
    tenant_id = request.state.tenant_id

    # Verify patient exists and belongs to tenant
    stmt = select(Paciente).where(Paciente.id == data.paciente_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Check if expediente already exists
    stmt = select(Expediente).where(Expediente.paciente_id == data.paciente_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="El paciente ya tiene un expediente activo")

    antecedentes_cifrado = None
    if data.antecedentes:
        stmt_key = select(TenantKey).where(TenantKey.tenant_id == tenant_id)
        tenant_key = (await db.execute(stmt_key)).scalar_one_or_none()
        if not tenant_key:
            raise HTTPException(status_code=500, detail="Tenant encryption key missing")
        antecedentes_cifrado = encrypt_field(
            data.antecedentes, tenant_key.encrypted_dek, tenant_id
        )

    expediente = Expediente(
        tenant_id=tenant_id,
        paciente_id=data.paciente_id,
        folio=data.numero_expediente or f"EXP-{data.paciente_id[:8].upper()}",
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
):
    stmt = select(Expediente).where(Expediente.paciente_id == paciente_id)
    expediente = (await db.execute(stmt)).scalar_one_or_none()

    if not expediente:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    antecedentes = None
    if expediente.antecedentes_cifrado:
        tenant_id = request.state.tenant_id
        stmt_key = select(TenantKey).where(TenantKey.tenant_id == tenant_id)
        tenant_key = (await db.execute(stmt_key)).scalar_one_or_none()
        if tenant_key:
            antecedentes = decrypt_field(
                expediente.antecedentes_cifrado, tenant_key.encrypted_dek, tenant_id
            )

    return {
        "id": str(expediente.id),
        "paciente_id": str(expediente.paciente_id),
        "numero_expediente": expediente.folio,
        "antecedentes": antecedentes,
        "creado_en": expediente.creado_en.isoformat()
    }

@router.put("/{expediente_id}/antecedentes")
async def update_antecedentes(
    expediente_id: UUID,
    data: ExpedienteUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    tenant_id = request.state.tenant_id

    stmt = select(Expediente).where(Expediente.id == expediente_id)
    expediente = (await db.execute(stmt)).scalar_one_or_none()
    
    if not expediente:
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    if data.antecedentes is not None:
        stmt_key = select(TenantKey).where(TenantKey.tenant_id == tenant_id)
        tenant_key = (await db.execute(stmt_key)).scalar_one_or_none()
        if not tenant_key:
            raise HTTPException(status_code=500, detail="Tenant encryption key missing")
        
        expediente.antecedentes_cifrado = encrypt_field(
            data.antecedentes, tenant_key.encrypted_dek, tenant_id
        )

    await db.flush()
    return {"status": "success"}
