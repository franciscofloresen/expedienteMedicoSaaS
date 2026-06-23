
"""API v1 — Pacientes CRUD (NOM-004 §5.3)."""

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.paciente import Paciente
from app.services.encryption import decrypt_field, encrypt_field

router = APIRouter()


# ── Pydantic Schemas (separate from NOM-004 validator) ──

class PacienteCreate(BaseModel):
    """Schema for creating a patient. Backend encrypts the address."""

    nombre_completo: str = Field(..., min_length=2, max_length=200)
    sexo: str = Field(..., pattern="^(M|F|X)$")
    fecha_nacimiento: date
    curp: str | None = Field(
        None, min_length=18, max_length=18, pattern=r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z\d]\d$"
    )
    entidad_nacimiento: str | None = None
    nacionalidad: str | None = None
    ocupacion: str | None = None
    telefono: str | None = None
    email: str | None = None
    aseguradora: str | None = None
    num_poliza: str | None = None
    domicilio: str | None = None  # Plaintext in, encrypted at rest

    @field_validator("fecha_nacimiento")
    def validate_fecha_nacimiento(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser en el futuro")
        return v


class PacienteUpdate(BaseModel):
    """Schema for updating a patient (all fields optional)."""

    nombre_completo: str | None = Field(None, min_length=2, max_length=200)
    sexo: str | None = Field(None, pattern="^(M|F|X)$")
    fecha_nacimiento: date | None = None
    curp: str | None = Field(
        None, min_length=18, max_length=18, pattern=r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z\d]\d$"
    )
    telefono: str | None = None
    email: str | None = None
    aseguradora: str | None = None
    num_poliza: str | None = None
    domicilio: str | None = None  # Will be encrypted before storage



# ── Endpoints ──

@router.get("/")
async def list_pacientes(
    request: Request,
    q: str | None = Query(None, min_length=2),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List patients for the current tenant (RLS filtered). Supports search by name, curp, phone."""
    stmt = select(Paciente).where(Paciente.activo == True)

    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            or_(
                Paciente.nombre_completo.ilike(search_term),
                Paciente.curp.ilike(search_term),
                Paciente.telefono.ilike(search_term)
            )
        )

    stmt = stmt.order_by(Paciente.nombre_completo).offset(skip).limit(limit)
    result = await db.execute(stmt)
    pacientes = result.scalars().all()

    # No encrypted fields in list view (performance + minimal exposure)
    return [
        {
            "id": str(p.id),
            "nombre_completo": p.nombre_completo,
            "curp": p.curp,
            "sexo": p.sexo,
            "fecha_nacimiento": p.fecha_nacimiento.isoformat(),
        }
        for p in pacientes
    ]


@router.post("/", status_code=201)
async def create_paciente(
    paciente_data: PacienteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new patient with NOM-004 required fields."""
    tenant_id = request.state.tenant_id

    # Encrypt address if provided
    domicilio_cifrado = None
    if paciente_data.domicilio:
        domicilio_cifrado = encrypt_field(paciente_data.domicilio, tenant_id)

    paciente = Paciente(
        tenant_id=tenant_id,
        nombre_completo=paciente_data.nombre_completo,
        sexo=paciente_data.sexo,
        fecha_nacimiento=paciente_data.fecha_nacimiento,
        curp=paciente_data.curp,
        entidad_nacimiento=paciente_data.entidad_nacimiento,
        nacionalidad=paciente_data.nacionalidad,
        ocupacion=paciente_data.ocupacion,
        telefono=paciente_data.telefono,
        email=paciente_data.email,
        aseguradora=paciente_data.aseguradora,
        num_poliza=paciente_data.num_poliza,
        domicilio_cifrado=domicilio_cifrado,
        creado_por=tenant_id,
    )
    db.add(paciente)
    await db.flush()

    return {"id": str(paciente.id), "nombre_completo": paciente.nombre_completo}


@router.get("/{paciente_id}")
async def get_paciente(
    paciente_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get patient details (decrypts address if present)."""
    stmt = select(Paciente).where(Paciente.id == paciente_id, Paciente.activo == True)
    result = await db.execute(stmt)
    paciente = result.scalar_one_or_none()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Decrypt address if present
    domicilio = None
    if paciente.domicilio_cifrado:
        tenant_id = request.state.tenant_id
        domicilio = decrypt_field(paciente.domicilio_cifrado, tenant_id)

    return {
        "id": str(paciente.id),
        "nombre_completo": paciente.nombre_completo,
        "sexo": paciente.sexo,
        "fecha_nacimiento": paciente.fecha_nacimiento.isoformat(),
        "curp": paciente.curp,
        "entidad_nacimiento": paciente.entidad_nacimiento,
        "nacionalidad": paciente.nacionalidad,
        "ocupacion": paciente.ocupacion,
        "telefono": paciente.telefono,
        "email": paciente.email,
        "aseguradora": paciente.aseguradora,
        "num_poliza": paciente.num_poliza,
        "domicilio": domicilio,
        "creado_en": paciente.creado_en.isoformat() if paciente.creado_en else None,
    }


@router.put("/{paciente_id}")
async def update_paciente(
    paciente_id: UUID,
    paciente_data: PacienteUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update patient details."""
    tenant_id = request.state.tenant_id

    stmt = select(Paciente).where(Paciente.id == paciente_id, Paciente.activo == True)
    paciente = (await db.execute(stmt)).scalar_one_or_none()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    update_data = paciente_data.model_dump(exclude_unset=True)

    # Handle address encryption if updated
    if "domicilio" in update_data:
        domicilio_texto = update_data.pop("domicilio")
        if domicilio_texto:
            update_data["domicilio_cifrado"] = encrypt_field(domicilio_texto, tenant_id)
        else:
            update_data["domicilio_cifrado"] = None

    for field, value in update_data.items():
        setattr(paciente, field, value)

    await db.flush()
    return {"status": "ok", "id": str(paciente.id)}


@router.delete("/{paciente_id}")
async def delete_paciente(
    paciente_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Soft delete a patient.
    NOM-004 forbids deleting medical records for 5 years, so we only hide them from the UI.
    """
    stmt = select(Paciente).where(Paciente.id == paciente_id, Paciente.activo == True)
    paciente = (await db.execute(stmt)).scalar_one_or_none()

    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")

    # Perform soft delete
    paciente.activo = False
    await db.flush()
    return {"status": "deleted"}
