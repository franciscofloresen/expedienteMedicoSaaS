import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.expediente import Expediente
from app.models.nota import Nota
from app.models.paciente import Paciente
from app.models.receta import Receta
from app.models.tenant import Tenant
from app.services.firma import sign_note
from app.services.verification import get_or_create_verification_token

router = APIRouter()


class RecetaCreate(BaseModel):
    nota_id: str
    medicamentos: list[dict[str, Any]]
    indicaciones_generales: str | None = None


def _tenant_uuid(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.tenant_id))


def _serialize_receta(receta: Receta) -> dict[str, Any]:
    return {
        "id": str(receta.id),
        "nota_id": str(receta.nota_id),
        "medicamentos": receta.medicamentos,
        "indicaciones_generales": receta.indicaciones_generales,
        "creado_en": receta.creado_en.isoformat(),
        "firmada_en": receta.firmada_en.isoformat() if receta.firmada_en else None,
        "firmada": receta.firma_digital is not None,
        "firma_hash_contenido": receta.firma_hash_contenido,
        "firma_algoritmo": receta.firma_algoritmo,
        "es_editable": receta.es_editable,
        "medico_nombre": receta.medico_nombre,
        "medico_cedula": receta.medico_cedula,
        "medico_especialidad": receta.medico_especialidad,
    }


async def _build_receta_print_payload(
    receta_id: uuid.UUID,
    request: Request,
    db: AsyncSession,
) -> dict[str, Any]:
    tenant_id = _tenant_uuid(request)
    stmt = (
        select(Receta, Nota, Expediente, Paciente)
        .join(Nota, Receta.nota_id == Nota.id)
        .join(Expediente, Nota.expediente_id == Expediente.id)
        .join(Paciente, Expediente.paciente_id == Paciente.id)
        .where(Receta.id == receta_id, Receta.tenant_id == tenant_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Receta no encontrada")

    receta, nota, expediente, paciente = row
    if not receta.firma_digital or not receta.firma_hash_contenido:
        raise HTTPException(status_code=400, detail="La receta debe estar firmada para imprimirse con QR")

    token_row, plain_token = await get_or_create_verification_token(
        db,
        tenant_id=tenant_id,
        resource_type="receta",
        resource_id=receta.id,
        public_metadata={
            "folio": f"REC-{str(receta.id)[:8].upper()}",
            "medico_nombre": receta.medico_nombre,
            "medico_cedula": receta.medico_cedula,
            "fecha_emision": receta.firmada_en.isoformat() if receta.firmada_en else None,
            "hash": receta.firma_hash_contenido,
        },
    )
    receta.verification_token_id = token_row.id

    return {
        "id": str(receta.id),
        "folio": f"REC-{str(receta.id)[:8].upper()}",
        "tipo_documento": "receta",
        "paciente": {
            "nombre_completo": paciente.nombre_completo,
            "fecha_nacimiento": paciente.fecha_nacimiento.isoformat(),
            "sexo": paciente.sexo,
            "alergias": paciente.alergias,
        },
        "expediente": {"id": str(expediente.id), "folio": expediente.folio},
        "nota_id": str(nota.id),
        "medico": {
            "nombre": receta.medico_nombre,
            "cedula": receta.medico_cedula,
            "especialidad": receta.medico_especialidad,
        },
        "medicamentos": receta.medicamentos,
        "indicaciones_generales": receta.indicaciones_generales,
        "fechas": {
            "creado_en": receta.creado_en.isoformat(),
            "firmado_en": receta.firmada_en.isoformat() if receta.firmada_en else None,
        },
        "firma": {
            "hash": receta.firma_hash_contenido,
            "algoritmo": receta.firma_algoritmo,
            "verification_url": f"{str(request.base_url).rstrip('/')}/verify/{plain_token}",
        },
        "leyenda": "Receta firmada digitalmente. El QR verifica metadatos mínimos sin mostrar medicamentos.",
    }


@router.post("")
async def create_receta(
    data: RecetaCreate, request: Request, db: AsyncSession = Depends(get_db)
) -> Any:
    tenant_id = _tenant_uuid(request)
    nota_id = uuid.UUID(data.nota_id)
    nota_stmt = select(Nota).where(Nota.id == nota_id, Nota.tenant_id == tenant_id)
    if not (await db.execute(nota_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    receta = Receta(
        tenant_id=tenant_id,
        nota_id=nota_id,
        medicamentos=data.medicamentos,
        indicaciones_generales=data.indicaciones_generales,
        es_editable=True,
    )
    db.add(receta)
    await db.flush()
    return _serialize_receta(receta)


@router.get("")
async def list_recetas(
    request: Request,
    nota_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    stmt = select(Receta).where(Receta.tenant_id == tenant_id)
    if nota_id:
        stmt = stmt.where(Receta.nota_id == uuid.UUID(nota_id))
    rows = (await db.execute(stmt.order_by(Receta.creado_en.desc()))).scalars().all()
    return [_serialize_receta(row) for row in rows]


@router.get("/{id}")
async def get_receta(id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    tenant_id = _tenant_uuid(request)
    stmt = select(Receta).where(Receta.id == uuid.UUID(id), Receta.tenant_id == tenant_id)
    receta = (await db.execute(stmt)).scalar_one_or_none()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    return _serialize_receta(receta)


@router.post("/{id}/firmar")
async def firmar_receta(id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    tenant_id = _tenant_uuid(request)
    receta_id = uuid.UUID(id)
    receta = (
        await db.execute(select(Receta).where(Receta.id == receta_id, Receta.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if not receta:
        raise HTTPException(status_code=404, detail="Receta no encontrada")
    if not receta.es_editable or receta.firma_digital:
        raise HTTPException(status_code=400, detail="La receta ya ha sido firmada")

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant or not tenant.cedula:
        raise HTTPException(status_code=400, detail="Cédula profesional requerida para firmar")

    content = json.dumps(
        {
            "id": str(receta.id),
            "nota_id": str(receta.nota_id),
            "medicamentos": receta.medicamentos,
            "indicaciones_generales": receta.indicaciones_generales,
            "creado_en": receta.creado_en.isoformat(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    signature_data = sign_note(
        content=content,
        tenant_id=str(tenant_id),
        nota_id=str(receta.id),
        medico_nombre=tenant.nombre_medico,
        medico_cedula=tenant.cedula,
        medico_especialidad=tenant.especialidad or "General",
    )
    receta.firma_digital = signature_data["firma_digital"]
    receta.firma_hash_contenido = signature_data["firma_hash_contenido"]
    receta.firma_kms_key_id = signature_data["firma_kms_key_id"]
    receta.firma_algoritmo = signature_data["firma_algoritmo"]
    receta.firmada_en = signature_data["firmado_en"]
    receta.medico_nombre = signature_data["medico_nombre"]
    receta.medico_cedula = signature_data["medico_cedula"]
    receta.medico_especialidad = signature_data["medico_especialidad"]
    receta.es_editable = False

    token_row, plain_token = await get_or_create_verification_token(
        db,
        tenant_id=tenant_id,
        resource_type="receta",
        resource_id=receta.id,
        public_metadata={
            "folio": f"REC-{str(receta.id)[:8].upper()}",
            "medico_nombre": receta.medico_nombre,
            "medico_cedula": receta.medico_cedula,
            "fecha_emision": receta.firmada_en.isoformat() if receta.firmada_en else None,
            "hash": receta.firma_hash_contenido,
        },
    )
    receta.verification_token_id = token_row.id
    await db.flush()
    payload = _serialize_receta(receta)
    payload["verification_url"] = f"{str(request.base_url).rstrip('/')}/verify/{plain_token}"
    return payload


@router.get("/{id}/print")
async def print_receta(id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    return await _build_receta_print_payload(uuid.UUID(id), request, db)
