"""API v1 — Notas Médicas y Firmas Digitales (NOM-004 §6)."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nom_validator import validar_nota_nom004
from app.db.session import get_db
from app.models.expediente import Expediente
from app.models.nota import Nota
from app.services.firma import sign_note

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

async def get_tenant_db(request: Request):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Missing tenant context")
    async for session in get_db(tenant_id):
        yield session

@router.post("/", status_code=201)
async def create_nota(
    data: NotaCreate,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Crear una nueva nota médica. 
    Se valida automáticamente que cumpla la NOM-004 mediante Pydantic (data).
    """
    tenant_id = request.state.tenant_id
    medico_id = getattr(request.state, "user_id", "local_dev_user") # from JWT usually

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
    )
    db.add(nota)
    await db.flush()

    return {"id": str(nota.id), "status": "creada, pendiente de firma"}


@router.get("/expediente/{expediente_id}")
async def list_notas_by_expediente(
    expediente_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
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
            "creado_en": n.creado_en.isoformat(),
        }
        for n in notas
    ]

@router.post("/{nota_id}/firmar")
async def firmar_nota(
    nota_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
):
    """
    Firma digitalmente la nota utilizando la llave asimétrica ECDSA P-256 en KMS.
    Calcula el hash SHA-256 del contenido canónico de la nota.
    """
    tenant_id = request.state.tenant_id

    stmt = select(Nota).where(Nota.id == nota_id)
    nota = (await db.execute(stmt)).scalar_one_or_none()

    if not nota:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    if nota.firma_digital:
        raise HTTPException(status_code=400, detail="La nota ya ha sido firmada")

    # Parse contenido back to dict
    contenido_dict = json.loads(nota.contenido) if nota.contenido else {}

    # Serialize content canonically
    content_dict = {
        "id": str(nota.id),
        "expediente_id": str(nota.expediente_id),
        "tipo_nota": nota.tipo_nota,
        "contenido": contenido_dict,
        "signos_vitales": nota.signos_vitales,
        "creado_en": nota.creado_en.isoformat(),
    }
    
    # In a real AWS environment, this calls KMS.
    # For local dev without credentials, it will raise a boto3 NoCredentialsError.
    try:
        signature_data = sign_note(
            content=json.dumps(content_dict),
            tenant_id=tenant_id,
            nota_id=nota_id,
            medico_nombre="Dr. Local Dev",
            medico_cedula="12345678"
        )
        nota.firma_digital = signature_data["firma_digital"].hex()
        nota.firmado_en = signature_data["firmado_en"]
        await db.flush()
        return {"id": str(nota.id), "firma_digital": nota.firma_digital, "firmado_en": nota.firmado_en.isoformat()}
    except Exception as e:
        logger.warning("KMS Signing Failed: %s", e)
        raise HTTPException(status_code=503, detail="El servicio de firma digital (KMS) no está disponible en este entorno.")
