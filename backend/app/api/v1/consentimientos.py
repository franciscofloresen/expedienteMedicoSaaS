import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.consentimiento import Consentimiento
from app.models.consentimiento_plantilla import (
    ConsentimientoPlantilla,
    ConsentimientoPlantillaVersion,
)
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.models.tenant import Tenant
from app.services.consent_templates import (
    LEGACY_TEMPLATES,
    load_catalog,
    render_consent_content,
    runtime_template_from_row,
    validate_template_fields,
)
from app.services.credenciales import get_credencial_para_firma
from app.services.firma import sign_note
from app.services.verification import (
    get_or_create_verification_token,
    public_verification_url,
)

router = APIRouter()


class ConsentimientoCreate(BaseModel):
    paciente_id: str
    expediente_id: str
    template_key: str
    procedimiento: str
    riesgos_principales: str | None = None


class FirmaPaciente(BaseModel):
    nombre_completo: str
    firma_paciente_base64: str
    aceptado: bool


def _tenant_uuid(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.tenant_id))


def _template_payload(
    template: ConsentimientoPlantilla,
    version: ConsentimientoPlantillaVersion,
) -> dict[str, Any]:
    runtime = runtime_template_from_row(version)
    return {
        "key": template.template_key,
        "nombre": runtime["nombre"],
        "version": runtime["version"],
        "descripcion": runtime["descripcion"],
        "riesgos": runtime["riesgos"],
        "categoria": template.categoria,
        "especialidad": template.especialidad,
        "procedimiento": template.procedimiento,
        "campos": runtime["campos"],
        "firmas_requeridas": runtime["firmas_requeridas"],
    }


def _fallback_payloads(
    especialidad: str | None = None,
    procedimiento: str | None = None,
) -> list[dict[str, Any]]:
    documents = load_catalog()
    results: list[dict[str, Any]] = []
    for document in documents:
        if especialidad and especialidad.casefold() not in (document.especialidad or "").casefold():
            continue
        if procedimiento and procedimiento.casefold() not in (
            document.procedimiento or document.nombre
        ).casefold():
            continue
        runtime = LEGACY_TEMPLATES[document.template_key]
        results.append(
            {
                "key": document.template_key,
                "nombre": runtime["nombre"],
                "version": runtime["version"],
                "descripcion": runtime["descripcion"],
                "riesgos": runtime["riesgos"],
                "categoria": document.categoria,
                "especialidad": document.especialidad,
                "procedimiento": document.procedimiento,
                "campos": runtime["campos"],
                "firmas_requeridas": runtime["firmas_requeridas"],
            }
        )
    return results


async def _published_count(db: AsyncSession) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(ConsentimientoPlantillaVersion)
                .where(ConsentimientoPlantillaVersion.estado == "publicada")
            )
        ).scalar_one()
    )


async def _resolve_template(
    db: AsyncSession, template_key: str
) -> tuple[dict[str, Any] | None, uuid.UUID | None]:
    row = (
        await db.execute(
            select(ConsentimientoPlantilla, ConsentimientoPlantillaVersion)
            .join(
                ConsentimientoPlantillaVersion,
                ConsentimientoPlantillaVersion.plantilla_id == ConsentimientoPlantilla.id,
            )
            .where(
                ConsentimientoPlantilla.template_key == template_key,
                ConsentimientoPlantilla.estado == "activa",
                ConsentimientoPlantillaVersion.estado == "publicada",
            )
        )
    ).first()
    if row:
        _template, version = row
        return runtime_template_from_row(version), version.id
    # Temporary rollout fallback: only while the new catalog is completely empty. Once
    # any version is published, a missing/retired key must not be resurrected from code.
    if await _published_count(db) == 0:
        return LEGACY_TEMPLATES.get(template_key), None
    return None, None


def _serialize(row: Consentimiento) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "paciente_id": str(row.paciente_id),
        "expediente_id": str(row.expediente_id),
        "template_key": row.template_key,
        "version": row.version,
        "plantilla_version_id": str(row.plantilla_version_id) if row.plantilla_version_id else None,
        "procedimiento": row.procedimiento,
        "contenido_renderizado": row.contenido_renderizado,
        "firmado_paciente_nombre": row.firmado_paciente_nombre,
        "firmado_paciente_en": row.firmado_paciente_en.isoformat() if row.firmado_paciente_en else None,
        "firmado_medico_en": row.firmado_medico_en.isoformat() if row.firmado_medico_en else None,
        "hash_contenido": row.hash_contenido,
        "status": row.status,
        "medico_nombre": row.medico_nombre,
        "medico_cedula": row.medico_cedula,
        "medico_especialidad": row.medico_especialidad,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/templates")
async def templates(
    especialidad: str | None = None,
    procedimiento: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    stmt = (
        select(ConsentimientoPlantilla, ConsentimientoPlantillaVersion)
        .join(
            ConsentimientoPlantillaVersion,
            ConsentimientoPlantillaVersion.plantilla_id == ConsentimientoPlantilla.id,
        )
        .where(
            ConsentimientoPlantilla.estado == "activa",
            ConsentimientoPlantillaVersion.estado == "publicada",
        )
        .order_by(ConsentimientoPlantilla.categoria, ConsentimientoPlantilla.template_key)
    )
    if especialidad:
        stmt = stmt.where(ConsentimientoPlantilla.especialidad.ilike(f"%{especialidad}%"))
    if procedimiento:
        stmt = stmt.where(ConsentimientoPlantilla.procedimiento.ilike(f"%{procedimiento}%"))
    rows = (await db.execute(stmt)).all()
    if rows:
        return [_template_payload(template, version) for template, version in rows]
    if await _published_count(db) == 0:
        return _fallback_payloads(especialidad, procedimiento)
    return []


@router.post("", status_code=201)
async def create_consentimiento(
    data: ConsentimientoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    template, plantilla_version_id = await _resolve_template(db, data.template_key)
    if not template:
        raise HTTPException(status_code=400, detail="Plantilla de consentimiento inválida")
    field_errors = validate_template_fields(
        template,
        {
            "procedimiento": data.procedimiento,
            "riesgos_principales": data.riesgos_principales,
        },
    )
    if field_errors:
        raise HTTPException(status_code=400, detail={"template_fields": field_errors})

    paciente_id = uuid.UUID(data.paciente_id)
    expediente_id = uuid.UUID(data.expediente_id)
    row = (
        await db.execute(
            select(Paciente, Expediente, Tenant)
            .join(Expediente, Expediente.paciente_id == Paciente.id)
            .join(Tenant, Tenant.id == Paciente.tenant_id)
            .where(
                Paciente.id == paciente_id,
                Expediente.id == expediente_id,
                Paciente.tenant_id == tenant_id,
                Expediente.tenant_id == tenant_id,
                Tenant.id == tenant_id,
            )
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Paciente o expediente no encontrado")

    paciente, _expediente, tenant = row
    credencial = await get_credencial_para_firma(db, tenant)
    riesgos = data.riesgos_principales or template["riesgos"]
    consentimiento = Consentimiento(
        tenant_id=tenant_id,
        paciente_id=paciente_id,
        expediente_id=expediente_id,
        template_key=data.template_key,
        version=template["version"],
        plantilla_version_id=plantilla_version_id,
        procedimiento=data.procedimiento,
        riesgos_principales=riesgos,
        contenido_renderizado=render_consent_content(
            template=template,
            paciente_nombre=paciente.nombre_completo,
            medico_nombre=credencial.nombre,
            medico_cedula=credencial.cedula,
            procedimiento=data.procedimiento,
            riesgos=riesgos,
        ),
        medico_nombre=credencial.nombre,
        medico_cedula=credencial.cedula,
        medico_especialidad=credencial.especialidad,
        status="draft",
    )
    db.add(consentimiento)
    await db.flush()
    return _serialize(consentimiento)


@router.get("/expediente/{expediente_id}")
async def list_by_expediente(
    expediente_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    rows = (
        await db.execute(
            select(Consentimiento)
            .where(
                Consentimiento.expediente_id == uuid.UUID(expediente_id),
                Consentimiento.tenant_id == tenant_id,
            )
            .order_by(Consentimiento.created_at.desc())
        )
    ).scalars().all()
    return [_serialize(row) for row in rows]


@router.get("/{id}")
async def get_consentimiento(id: str, request: Request, db: AsyncSession = Depends(get_db)) -> Any:
    row = (
        await db.execute(
            select(Consentimiento).where(
                Consentimiento.id == uuid.UUID(id),
                Consentimiento.tenant_id == _tenant_uuid(request),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    return _serialize(row)


@router.post("/{id}/firmar-paciente")
async def firmar_paciente(
    id: str,
    data: FirmaPaciente,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    if not data.aceptado:
        raise HTTPException(status_code=400, detail="El paciente debe aceptar el consentimiento")
    row = (
        await db.execute(
            select(Consentimiento).where(
                Consentimiento.id == uuid.UUID(id),
                Consentimiento.tenant_id == _tenant_uuid(request),
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    if row.firmado_paciente_en:
        raise HTTPException(status_code=400, detail="El paciente ya firmó este consentimiento")

    row.firma_paciente_base64 = data.firma_paciente_base64
    row.firmado_paciente_nombre = data.nombre_completo
    row.firmado_paciente_en = datetime.now(timezone.utc)
    row.status = "signed_patient"
    await db.flush()
    return _serialize(row)


@router.post("/{id}/firmar-medico")
async def firmar_medico(
    id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    row = (
        await db.execute(
            select(Consentimiento).where(
                Consentimiento.id == uuid.UUID(id),
                Consentimiento.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    if not row.firmado_paciente_en:
        raise HTTPException(status_code=400, detail="Primero debe firmar el paciente")
    if row.firmado_medico_en:
        raise HTTPException(status_code=400, detail="El consentimiento ya fue firmado por el médico")
    if not row.medico_cedula:
        raise HTTPException(status_code=400, detail="Cédula profesional requerida para firmar")

    content = json.dumps(
        {
            "id": str(row.id),
            "paciente_id": str(row.paciente_id),
            "expediente_id": str(row.expediente_id),
            "template_key": row.template_key,
            "version": row.version,
            "procedimiento": row.procedimiento,
            "contenido_renderizado": row.contenido_renderizado,
            "firmado_paciente_nombre": row.firmado_paciente_nombre,
            "firmado_paciente_en": row.firmado_paciente_en.isoformat(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    signature_data = sign_note(
        content=content,
        tenant_id=str(tenant_id),
        nota_id=str(row.id),
        medico_nombre=row.medico_nombre or "",
        medico_cedula=row.medico_cedula,
        medico_especialidad=row.medico_especialidad or "General",
    )
    row.firma_digital = signature_data["firma_digital"]
    row.hash_contenido = signature_data["firma_hash_contenido"]
    row.firmado_medico_en = signature_data["firmado_en"]
    row.status = "signed"
    token_row, plain_token = await get_or_create_verification_token(
        db,
        tenant_id=tenant_id,
        resource_type="consentimiento",
        resource_id=row.id,
        public_metadata={
            "folio": f"CONS-{str(row.id)[:8].upper()}",
            "medico_nombre": row.medico_nombre,
            "medico_cedula": row.medico_cedula,
            "fecha_emision": row.firmado_medico_en.isoformat() if row.firmado_medico_en else None,
            "hash": row.hash_contenido,
        },
    )
    row.verification_token_id = token_row.id
    await db.flush()
    payload = _serialize(row)
    payload["verification_url"] = public_verification_url(plain_token)
    return payload


@router.get("/{id}/print")
async def print_consentimiento(
    id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    stmt = (
        select(Consentimiento, Paciente, Expediente)
        .join(Paciente, Consentimiento.paciente_id == Paciente.id)
        .join(Expediente, Consentimiento.expediente_id == Expediente.id)
        .where(Consentimiento.id == uuid.UUID(id), Consentimiento.tenant_id == tenant_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    consentimiento, paciente, expediente = row
    if not consentimiento.hash_contenido:
        raise HTTPException(status_code=400, detail="El consentimiento debe estar firmado por el médico")
    token_row, plain_token = await get_or_create_verification_token(
        db,
        tenant_id=tenant_id,
        resource_type="consentimiento",
        resource_id=consentimiento.id,
        public_metadata={
            "folio": f"CONS-{str(consentimiento.id)[:8].upper()}",
            "medico_nombre": consentimiento.medico_nombre,
            "medico_cedula": consentimiento.medico_cedula,
            "fecha_emision": consentimiento.firmado_medico_en.isoformat() if consentimiento.firmado_medico_en else None,
            "hash": consentimiento.hash_contenido,
        },
    )
    consentimiento.verification_token_id = token_row.id
    return {
        **_serialize(consentimiento),
        "folio": f"CONS-{str(consentimiento.id)[:8].upper()}",
        "tipo_documento": "consentimiento",
        "paciente": {
            "nombre_completo": paciente.nombre_completo,
            "fecha_nacimiento": paciente.fecha_nacimiento.isoformat(),
            "sexo": paciente.sexo,
        },
        "expediente": {"id": str(expediente.id), "folio": expediente.folio},
        "firma": {
            "hash": consentimiento.hash_contenido,
            "verification_url": public_verification_url(plain_token),
        },
        "leyenda": "Consentimiento firmado en dispositivo del consultorio y verificable por QR.",
    }
