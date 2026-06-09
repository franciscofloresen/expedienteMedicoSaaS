"""API v1 — Notas Médicas y Firmas Digitales (NOM-004 §6)."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nom_validator import validar_nota_nom004
from app.db.session import get_db
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.models.nota import Nota
from app.services.firma import sign_note, verify_signature

logger = logging.getLogger("medrecord")

router = APIRouter()

class NotaCreate(BaseModel):
    expediente_id: str
    tipo_nota: str = Field(..., description="evolucion, interconsulta, ingreso, egreso")
    contenido: dict[str, Any]
    signos_vitales: dict[str, Any] = Field(default_factory=dict)
    diagnosticos: list[str] = Field(default_factory=list)
    tratamiento: str | None = None
    diagnostico_cie10: str | None = None

class NotaUpdate(BaseModel):
    contenido: dict[str, Any] | None = None
    signos_vitales: dict[str, Any] | None = None
    diagnosticos: list[str] | None = None
    tratamiento: str | None = None
    diagnostico_cie10: str | None = None

@router.get("/")
async def list_notas(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all notes across the clinic, with patient info."""
    stmt = (
        select(Nota, Expediente, Paciente)
        .join(Expediente, Nota.expediente_id == Expediente.id)
        .join(Paciente, Expediente.paciente_id == Paciente.id)
        .order_by(desc(Nota.creado_en))
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": str(nota.id),
            "tipo_nota": nota.tipo_nota,
            "firmada": nota.firma_digital is not None,
            "creado_en": nota.creado_en.isoformat(),
            "firmado_en": nota.firmado_en.isoformat() if nota.firmado_en else None,
            "medico_nombre": nota.medico_nombre,
            "expediente_id": str(exp.id),
            "expediente_folio": exp.folio,
            "paciente_id": str(pac.id),
            "paciente_nombre": pac.nombre_completo,
            "diagnostico_cie10": nota.diagnostico_cie10,
        }
        for nota, exp, pac in rows
    ]

@router.post("/", status_code=201)
async def create_nota(
    data: NotaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Crear una nueva nota médica (borrador).
    Se valida automáticamente que cumpla la NOM-004 mediante Pydantic (data).
    La nota se crea como borrador (es_editable=true) y debe firmarse por separado.
    """
    tenant_id = request.state.tenant_id

    # Verify expediente exists
    stmt = select(Expediente).where(Expediente.id == data.expediente_id)
    if not (await db.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Expediente no encontrado")

    # Validate the note payload against NOM-004 rules based on the note type.
    try:
        validar_nota_nom004(data.tipo_nota, {
            **data.contenido,
            "signos_vitales": data.signos_vitales,
            "diagnostico": data.diagnosticos[0] if data.diagnosticos else "",
            "tratamiento": data.tratamiento,
        })
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Serialize all clinical content into the `contenido` Text column
    contenido_completo = json.dumps({
        **data.contenido,
        "diagnosticos": data.diagnosticos,
        "tratamiento": data.tratamiento,
    }, ensure_ascii=False)

    nota = Nota(
        tenant_id=tenant_id,
        expediente_id=str(data.expediente_id),
        tipo_nota=data.tipo_nota,
        contenido=contenido_completo,
        signos_vitales=data.signos_vitales,
        diagnostico_cie10=data.diagnostico_cie10,
        creado_por=tenant_id,
        es_editable=True,
    )
    db.add(nota)
    await db.flush()

    return {"id": str(nota.id), "status": "creada, pendiente de firma"}


@router.put("/{nota_id}")
async def update_nota(
    nota_id: str,
    data: NotaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Actualizar una nota médica (solo si es editable / no firmada).
    NOM-004: Signed notes are immutable. Corrections must be amendments.
    """
    stmt = select(Nota).where(Nota.id == nota_id)
    nota = (await db.execute(stmt)).scalar_one_or_none()

    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    if not nota.es_editable:
        raise HTTPException(
            status_code=403,
            detail="La nota ya ha sido firmada y no puede modificarse. "
                   "Según la NOM-004, las correcciones deben realizarse como notas de adenda."
        )

    if data.contenido is not None or data.diagnosticos is not None or data.tratamiento is not None:
        current = json.loads(nota.contenido) if nota.contenido else {}
        if data.contenido is not None:
            current.update(data.contenido)
        if data.diagnosticos is not None:
            current["diagnosticos"] = data.diagnosticos
        if data.tratamiento is not None:
            current["tratamiento"] = data.tratamiento
        nota.contenido = json.dumps(current, ensure_ascii=False)

    if data.signos_vitales is not None:
        nota.signos_vitales = data.signos_vitales

    if data.diagnostico_cie10 is not None:
        nota.diagnostico_cie10 = data.diagnostico_cie10

    await db.flush()

    return {"id": str(nota.id), "status": "actualizada"}


@router.get("/expediente/{expediente_id}")
async def list_notas_by_expediente(
    expediente_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las notas de un expediente, ordenadas por fecha."""
    stmt = (
        select(Nota)
        .where(Nota.expediente_id == expediente_id)
        .order_by(Nota.creado_en.desc())
    )
    result = await db.execute(stmt)
    notas = result.scalars().all()

    return [
        {
            "id": str(n.id),
            "tipo_nota": n.tipo_nota,
            "contenido": json.loads(n.contenido) if n.contenido else {},
            "signos_vitales": n.signos_vitales,
            "firmada": n.firma_digital is not None,
            "es_editable": n.es_editable,
            "firmado_en": n.firmado_en.isoformat() if n.firmado_en else None,
            "medico_nombre": n.medico_nombre,
            "medico_cedula": n.medico_cedula,
            "medico_especialidad": n.medico_especialidad,
            "firma_hash_contenido": n.firma_hash_contenido,
            "firma_kms_key_id": n.firma_kms_key_id,
            "firma_algoritmo": n.firma_algoritmo,
            "creado_en": n.creado_en.isoformat(),
        }
        for n in notas
    ]

@router.post("/{nota_id}/firmar")
async def firmar_nota(
    nota_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Firma digitalmente la nota utilizando ECDSA P-256.
    En producción: vía AWS KMS. En desarrollo: llave local efímera.

    Stores ALL signature metadata for legal audit and verification:
    - firma_digital: the ECDSA signature bytes
    - firma_hash_contenido: SHA-256 hash of the canonical payload
    - firma_kms_key_id: KMS key ARN or "local-dev-key"
    - firma_algoritmo: always ECDSA_SHA_256
    - firmado_por: user ID from JWT
    - firmado_en: signing timestamp
    - medico_nombre: doctor name snapshot
    - medico_cedula: doctor license snapshot
    - medico_especialidad: doctor specialty snapshot
    - es_editable: set to false (immutable after signing)
    """
    tenant_id = request.state.tenant_id
    user_id = getattr(request.state, "user_id", None)

    stmt = select(Nota).where(Nota.id == nota_id)
    nota = (await db.execute(stmt)).scalar_one_or_none()

    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    if not nota.es_editable:
        raise HTTPException(status_code=400, detail="La nota ya ha sido firmada")

    if nota.firma_digital:
        raise HTTPException(status_code=400, detail="La nota ya ha sido firmada")

    # Parse contenido back to dict for canonical serialization
    contenido_dict = json.loads(nota.contenido) if nota.contenido else {}

    # Build the content that gets signed
    content_to_sign = json.dumps({
        "id": str(nota.id),
        "expediente_id": str(nota.expediente_id),
        "tipo_nota": nota.tipo_nota,
        "contenido": contenido_dict,
        "signos_vitales": nota.signos_vitales,
        "creado_en": nota.creado_en.isoformat(),
    }, ensure_ascii=False, sort_keys=True)

    # TODO: In production, pull doctor identity from tenant/user profile
    # For now, use placeholder values in dev; real values from JWT claims in prod
    medico_nombre = getattr(request.state, "user_name", "Dr. Local Dev")
    medico_cedula = getattr(request.state, "user_cedula", "DEV-00000")
    medico_especialidad = getattr(request.state, "user_especialidad", "General")

    try:
        signature_data = sign_note(
            content=content_to_sign,
            tenant_id=tenant_id,
            nota_id=nota_id,
            medico_nombre=medico_nombre,
            medico_cedula=medico_cedula,
            medico_especialidad=medico_especialidad,
        )

        # Persist ALL signature metadata (9 fields)
        nota.firma_digital = signature_data["firma_digital"]
        nota.firma_hash_contenido = signature_data["firma_hash_contenido"]
        nota.firma_kms_key_id = signature_data["firma_kms_key_id"]
        nota.firma_algoritmo = signature_data["firma_algoritmo"]
        nota.firmado_en = signature_data["firmado_en"]
        nota.firmado_por = user_id
        nota.medico_nombre = signature_data["medico_nombre"]
        nota.medico_cedula = signature_data["medico_cedula"]
        nota.medico_especialidad = signature_data["medico_especialidad"]

        # Lock the note — NOM-004: signed notes are immutable
        nota.es_editable = False

        await db.flush()

        return {
            "id": str(nota.id),
            "firmada": True,
            "firma_hash_contenido": nota.firma_hash_contenido,
            "firmado_en": nota.firmado_en.isoformat(),
            "medico_nombre": nota.medico_nombre,
            "medico_cedula": nota.medico_cedula,
            "es_editable": False,
        }
    except Exception as e:
        logger.warning("Signing failed for nota %s: %s", nota_id, e)
        raise HTTPException(
            status_code=503,
            detail="El servicio de firma digital no está disponible en este entorno."
        )


@router.get("/{nota_id}/verificar-firma")
async def verificar_firma(
    nota_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Verify the digital signature on a signed medical note.

    Reconstructs the canonical payload from stored metadata
    and verifies the ECDSA signature using KMS or the local dev key.
    """
    stmt = select(Nota).where(Nota.id == nota_id)
    nota = (await db.execute(stmt)).scalar_one_or_none()

    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    if not nota.firma_digital:
        return {
            "nota_id": str(nota.id),
            "firmada": False,
            "valid": False,
            "detail": "La nota no ha sido firmada",
        }

    # Reconstruct the signed content exactly as it was at signing time
    contenido_dict = json.loads(nota.contenido) if nota.contenido else {}
    content_to_verify = json.dumps({
        "id": str(nota.id),
        "expediente_id": str(nota.expediente_id),
        "tipo_nota": nota.tipo_nota,
        "contenido": contenido_dict,
        "signos_vitales": nota.signos_vitales,
        "creado_en": nota.creado_en.isoformat(),
    }, ensure_ascii=False, sort_keys=True)

    # Reconstruct signing metadata
    signing_metadata = {
        "tenant_id": str(nota.tenant_id),
        "nota_id": str(nota.id),
        "medico_nombre": nota.medico_nombre or "",
        "medico_cedula": nota.medico_cedula or "",
        "medico_especialidad": nota.medico_especialidad or "",
        "timestamp": nota.firmado_en.isoformat() if nota.firmado_en else "",
    }

    # Handle signature bytes — may be stored as hex string or bytes
    signature_bytes = nota.firma_digital
    if isinstance(signature_bytes, str):
        signature_bytes = bytes.fromhex(signature_bytes)

    try:
        is_valid = verify_signature(
            content=content_to_verify,
            metadata=signing_metadata,
            signature=signature_bytes,
            stored_hash=nota.firma_hash_contenido or "",
            key_id=nota.firma_kms_key_id or "",
        )
    except Exception as e:
        logger.error("Signature verification failed for nota %s: %s", nota_id, e)
        return {
            "nota_id": str(nota.id),
            "firmada": True,
            "valid": False,
            "detail": "Error al verificar la firma",
        }

    return {
        "nota_id": str(nota.id),
        "firmada": True,
        "valid": is_valid,
        "firma_hash_contenido": nota.firma_hash_contenido,
        "firmado_en": nota.firmado_en.isoformat() if nota.firmado_en else None,
        "medico_nombre": nota.medico_nombre,
        "medico_cedula": nota.medico_cedula,
        "medico_especialidad": nota.medico_especialidad,
        "firma_algoritmo": nota.firma_algoritmo,
    }
