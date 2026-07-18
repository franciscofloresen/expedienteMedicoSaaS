import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import (
    ConsentimientoDocumentoFinal,
    ConsentimientoFirmante,
    ConsentimientoRevocacion,
)
from app.models.consentimiento_plantilla import (
    ConsentimientoPlantilla,
    ConsentimientoPlantillaVersion,
)
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.models.tenant import Tenant
from app.models.verification_token import VerificationToken
from app.services.consent_documents import (
    build_final_consent_pdf,
    final_consent_download_url,
    store_final_consent_pdf,
)
from app.services.consent_signatures import canonical_consent_content, normalize_signature
from app.services.consent_templates import (
    LEGACY_TEMPLATES,
    load_catalog,
    render_consent_content,
    runtime_template_from_row,
    validate_template_fields,
)
from app.services.credenciales import (
    get_credencial_para_firma,
    get_credencial_seleccionada_para_firma,
    list_credenciales_para_firma,
)
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


class FirmaTestigo(BaseModel):
    nombre_completo: str = Field(min_length=1, max_length=200)
    firma_base64: str


class FirmaPaciente(BaseModel):
    nombre_completo: str = Field(min_length=1, max_length=200)
    firma_paciente_base64: str
    aceptado: bool
    tipo_firmante: Literal["paciente", "representante", "tutor"] = "paciente"
    relacion_paciente: str | None = Field(default=None, max_length=120)
    motivo_representacion: str | None = Field(default=None, max_length=2_000)
    testigos: list[FirmaTestigo] = Field(default_factory=list, max_length=2)


class FirmaMedico(BaseModel):
    credencial_id: str | None = None


class RevocacionCreate(BaseModel):
    motivo: str = Field(min_length=10, max_length=2_000)


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
    from app.core.clinical_rollout import feature_enabled

    if not feature_enabled("consent_template_engine"):
        return LEGACY_TEMPLATES.get(template_key), None
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


def _serialize(
    row: Consentimiento,
    *,
    firmantes: list[ConsentimientoFirmante] | None = None,
    documento: ConsentimientoDocumentoFinal | None = None,
    revocacion: ConsentimientoRevocacion | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
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
        "firma_algoritmo": row.firma_algoritmo,
        "status": row.status,
        "medico_id": str(row.medico_id) if row.medico_id else None,
        "credencial_id": str(row.credencial_id) if row.credencial_id else None,
        "medico_nombre": row.medico_nombre,
        "medico_cedula": row.medico_cedula,
        "medico_especialidad": row.medico_especialidad,
        "created_at": row.created_at.isoformat(),
    }
    payload["firmantes"] = [
        {
            "id": str(signer.id),
            "tipo": signer.tipo,
            "orden": signer.orden,
            "nombre": signer.nombre,
            "relacion_paciente": signer.relacion_paciente,
            "motivo_representacion": signer.motivo_representacion,
            "firma_sha256": signer.firma_sha256,
            "firmado_en": signer.firmado_en.isoformat(),
        }
        for signer in (firmantes or [])
    ]
    payload["documento_final"] = (
        {
            "id": str(documento.id),
            "s3_key": documento.s3_key,
            "s3_version_id": documento.s3_version_id,
            "contenido_sha256": documento.contenido_sha256,
            "content_type": documento.content_type,
            "size_bytes": documento.size_bytes,
            "creado_en": documento.creado_en.isoformat(),
        }
        if documento
        else None
    )
    payload["revocacion"] = (
        {
            "id": str(revocacion.id),
            "motivo": revocacion.motivo,
            "actor_nombre": revocacion.actor_nombre,
            "actor_tipo": revocacion.actor_tipo,
            "revocado_en": revocacion.revocado_en.isoformat(),
        }
        if revocacion
        else None
    )
    return payload


async def _evidence_for_consent(
    db: AsyncSession, consentimiento_id: uuid.UUID
) -> tuple[
    list[ConsentimientoFirmante],
    ConsentimientoDocumentoFinal | None,
    ConsentimientoRevocacion | None,
]:
    firmantes = (
        await db.execute(
            select(ConsentimientoFirmante)
            .where(ConsentimientoFirmante.consentimiento_id == consentimiento_id)
            .order_by(ConsentimientoFirmante.tipo, ConsentimientoFirmante.orden)
        )
    ).scalars().all()
    documento = (
        await db.execute(
            select(ConsentimientoDocumentoFinal).where(
                ConsentimientoDocumentoFinal.consentimiento_id == consentimiento_id
            )
        )
    ).scalar_one_or_none()
    revocacion = (
        await db.execute(
            select(ConsentimientoRevocacion).where(
                ConsentimientoRevocacion.consentimiento_id == consentimiento_id
            )
        )
    ).scalar_one_or_none()
    return list(firmantes), documento, revocacion


async def _evidence_for_consents(
    db: AsyncSession, consentimiento_ids: list[uuid.UUID]
) -> dict[
    uuid.UUID,
    tuple[
        list[ConsentimientoFirmante],
        ConsentimientoDocumentoFinal | None,
        ConsentimientoRevocacion | None,
    ],
]:
    """Load lateral evidence in three bounded queries, independent of row count."""
    if not consentimiento_ids:
        return {}

    firmantes = (
        await db.execute(
            select(ConsentimientoFirmante)
            .where(ConsentimientoFirmante.consentimiento_id.in_(consentimiento_ids))
            .order_by(
                ConsentimientoFirmante.consentimiento_id,
                ConsentimientoFirmante.tipo,
                ConsentimientoFirmante.orden,
            )
        )
    ).scalars().all()
    documentos = (
        await db.execute(
            select(ConsentimientoDocumentoFinal).where(
                ConsentimientoDocumentoFinal.consentimiento_id.in_(consentimiento_ids)
            )
        )
    ).scalars().all()
    revocaciones = (
        await db.execute(
            select(ConsentimientoRevocacion).where(
                ConsentimientoRevocacion.consentimiento_id.in_(consentimiento_ids)
            )
        )
    ).scalars().all()

    grouped_signers: dict[uuid.UUID, list[ConsentimientoFirmante]] = {
        row_id: [] for row_id in consentimiento_ids
    }
    for signer in firmantes:
        grouped_signers[signer.consentimiento_id].append(signer)
    document_by_id = {row.consentimiento_id: row for row in documentos}
    revocation_by_id = {row.consentimiento_id: row for row in revocaciones}
    return {
        row_id: (
            grouped_signers[row_id],
            document_by_id.get(row_id),
            revocation_by_id.get(row_id),
        )
        for row_id in consentimiento_ids
    }


async def _signature_requirements(
    db: AsyncSession, consentimiento: Consentimiento
) -> dict[str, Any]:
    if consentimiento.plantilla_version_id:
        requirements = (
            await db.execute(
                select(ConsentimientoPlantillaVersion.firmas_requeridas).where(
                    ConsentimientoPlantillaVersion.id == consentimiento.plantilla_version_id
                )
            )
        ).scalar_one_or_none()
        if requirements is not None:
            return dict(requirements)
    template = LEGACY_TEMPLATES.get(consentimiento.template_key)
    return dict(
        (template or {}).get("firmas_requeridas")
        or {"paciente": True, "medico": True, "testigos": 0}
    )


async def _legacy_sign_patient(
    db: AsyncSession, row: Consentimiento, data: FirmaPaciente
) -> dict[str, Any]:
    """Stage-7 rollback path: retain the pre-Fase-5 patient snapshot contract."""
    try:
        normalized = normalize_signature(data.firma_paciente_base64)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row.firma_paciente_base64 = normalized.data_url
    row.firmado_paciente_nombre = data.nombre_completo.strip()
    row.firmado_paciente_en = datetime.now(timezone.utc)
    row.status = "signed_patient"
    await db.flush()
    return _serialize(row)


async def _legacy_sign_doctor(
    db: AsyncSession, row: Consentimiento, tenant_id: uuid.UUID
) -> dict[str, Any]:
    """Stage-7 rollback path: sign without Fase-5 lateral evidence/S3 finalization."""
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
            "firmado_paciente_en": (
                row.firmado_paciente_en.isoformat() if row.firmado_paciente_en else None
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    signature_data = sign_note(
        content=content,
        tenant_id=str(tenant_id),
        nota_id=str(row.id),
        medico_nombre=row.medico_nombre or "",
        medico_cedula=row.medico_cedula or "",
        medico_especialidad=row.medico_especialidad or "General",
    )
    row.firma_digital = signature_data["firma_digital"]
    row.hash_contenido = signature_data["firma_hash_contenido"]
    row.firma_kms_key_id = signature_data["firma_kms_key_id"]
    row.firma_algoritmo = signature_data["firma_algoritmo"]
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
            "fecha_emision": row.firmado_medico_en.isoformat(),
            "hash": row.hash_contenido,
            "firma_algoritmo": row.firma_algoritmo,
        },
    )
    row.verification_token_id = token_row.id
    await db.flush()
    payload = _serialize(row)
    payload["verification_url"] = public_verification_url(plain_token)
    return payload


@router.get("/templates")
async def templates(
    especialidad: str | None = None,
    procedimiento: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    from app.core.clinical_rollout import feature_enabled

    if not feature_enabled("consent_template_engine"):
        return _fallback_payloads(especialidad, procedimiento)
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


@router.get("/credenciales-firma")
async def credenciales_firma(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Active professional credentials that can be selected for final signature."""
    return await list_credenciales_para_firma(db, _tenant_uuid(request))


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
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    stmt = (
        select(Consentimiento)
        .where(
            Consentimiento.expediente_id == uuid.UUID(expediente_id),
            Consentimiento.tenant_id == tenant_id,
        )
        .order_by(Consentimiento.created_at.desc(), Consentimiento.id.desc())
    )
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    evidence = await _evidence_for_consents(db, [row.id for row in rows])
    return [
        _serialize(
            row,
            firmantes=evidence[row.id][0],
            documento=evidence[row.id][1],
            revocacion=evidence[row.id][2],
        )
        for row in rows
    ]


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
    firmantes, documento, revocacion = await _evidence_for_consent(db, row.id)
    return _serialize(row, firmantes=firmantes, documento=documento, revocacion=revocacion)


@router.post("/{id}/firmar-paciente")
async def firmar_paciente(
    id: str,
    data: FirmaPaciente,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    if not data.aceptado:
        raise HTTPException(status_code=400, detail="El paciente debe aceptar el consentimiento")
    tenant_id = _tenant_uuid(request)
    row = (
        await db.execute(
            select(Consentimiento)
            .where(
                Consentimiento.id == uuid.UUID(id),
                Consentimiento.tenant_id == tenant_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    if row.firmado_paciente_en:
        raise HTTPException(status_code=400, detail="El paciente ya firmó este consentimiento")
    if row.firmado_medico_en:
        raise HTTPException(status_code=409, detail="El consentimiento ya está finalizado")

    from app.core.clinical_rollout import feature_enabled

    if not feature_enabled("consent_finalization"):
        return await _legacy_sign_patient(db, row, data)

    requirements = await _signature_requirements(db, row)
    required_witnesses = int(requirements.get("testigos") or 0)
    if len(data.testigos) != required_witnesses:
        raise HTTPException(
            status_code=400,
            detail=f"La plantilla requiere exactamente {required_witnesses} testigo(s)",
        )
    if data.tipo_firmante != "paciente" and (
        not (data.relacion_paciente or "").strip()
        or not (data.motivo_representacion or "").strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="Representante o tutor requiere relación con el paciente y motivo",
        )
    try:
        main_signature = normalize_signature(data.firma_paciente_base64)
        witness_signatures = [normalize_signature(item.firma_base64) for item in data.testigos]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    signed_at = datetime.now(timezone.utc)
    db.add(
        ConsentimientoFirmante(
            tenant_id=tenant_id,
            consentimiento_id=row.id,
            tipo=data.tipo_firmante,
            orden=0,
            nombre=data.nombre_completo.strip(),
            relacion_paciente=(data.relacion_paciente or "").strip() or None,
            motivo_representacion=(data.motivo_representacion or "").strip() or None,
            firma_base64=main_signature.data_url,
            firma_sha256=main_signature.sha256,
            firmado_en=signed_at,
        )
    )
    for order, (witness, normalized) in enumerate(
        zip(data.testigos, witness_signatures, strict=True), start=1
    ):
        db.add(
            ConsentimientoFirmante(
                tenant_id=tenant_id,
                consentimiento_id=row.id,
                tipo="testigo",
                orden=order,
                nombre=witness.nombre_completo.strip(),
                firma_base64=normalized.data_url,
                firma_sha256=normalized.sha256,
                firmado_en=signed_at,
            )
        )

    # Legacy snapshot stays populated for compatibility; normalized evidence lives in
    # consentimiento_firmantes and is what the final canonical document signs.
    row.firma_paciente_base64 = main_signature.data_url
    row.firmado_paciente_nombre = data.nombre_completo.strip()
    row.firmado_paciente_en = signed_at
    row.status = "signed_patient"
    await db.flush()
    firmantes, documento, revocacion = await _evidence_for_consent(db, row.id)
    return _serialize(row, firmantes=firmantes, documento=documento, revocacion=revocacion)


@router.post("/{id}/firmar-medico")
async def firmar_medico(
    id: str,
    request: Request,
    data: FirmaMedico | None = None,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    result = (
        await db.execute(
            select(Consentimiento, Paciente, Expediente, Tenant)
            .join(Paciente, Paciente.id == Consentimiento.paciente_id)
            .join(Expediente, Expediente.id == Consentimiento.expediente_id)
            .join(Tenant, Tenant.id == Consentimiento.tenant_id)
            .where(Consentimiento.id == uuid.UUID(id), Consentimiento.tenant_id == tenant_id)
            .with_for_update(of=Consentimiento)
        )
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    row, paciente, expediente, tenant = result
    if not row.firmado_paciente_en:
        raise HTTPException(status_code=400, detail="Primero debe firmar el paciente")
    if row.firmado_medico_en:
        raise HTTPException(status_code=400, detail="El consentimiento ya fue firmado por el médico")

    from app.core.clinical_rollout import feature_enabled

    if not feature_enabled("consent_finalization"):
        if not row.medico_cedula:
            raise HTTPException(status_code=400, detail="Cédula profesional requerida para firmar")
        return await _legacy_sign_doctor(db, row, tenant_id)
    firmantes, existing_document, revocacion = await _evidence_for_consent(db, row.id)
    if existing_document is not None:
        raise HTTPException(status_code=409, detail="El documento final ya existe")
    if revocacion is not None:
        raise HTTPException(status_code=409, detail="El consentimiento está revocado")
    requirements = await _signature_requirements(db, row)
    main_signers = [signer for signer in firmantes if signer.tipo != "testigo"]
    witnesses = [signer for signer in firmantes if signer.tipo == "testigo"]
    required_witnesses = int(requirements.get("testigos") or 0)
    if len(main_signers) != 1 or len(witnesses) != required_witnesses:
        raise HTTPException(
            status_code=400,
            detail="No se han capturado todos los firmantes requeridos por la plantilla",
        )

    try:
        credencial_id = uuid.UUID(data.credencial_id) if data and data.credencial_id else None
        credencial = await get_credencial_seleccionada_para_firma(db, tenant, credencial_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not credencial.cedula:
        raise HTTPException(status_code=400, detail="Cédula profesional requerida para firmar")
    row.medico_id = credencial.medico_id
    row.credencial_id = credencial.credencial_id
    row.medico_nombre = credencial.nombre
    row.medico_cedula = credencial.cedula
    row.medico_especialidad = credencial.especialidad

    content = canonical_consent_content(row, firmantes)
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
    row.firma_kms_key_id = signature_data["firma_kms_key_id"]
    row.firma_algoritmo = signature_data["firma_algoritmo"]
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
            "firma_algoritmo": row.firma_algoritmo,
        },
    )
    row.verification_token_id = token_row.id
    verification_url = public_verification_url(plain_token)
    pdf_bytes = build_final_consent_pdf(
        consentimiento=row,
        paciente=paciente,
        expediente=expediente,
        firmantes=firmantes,
        verification_url=verification_url,
    )
    stored = store_final_consent_pdf(
        tenant_id=str(tenant_id), consentimiento_id=str(row.id), pdf_bytes=pdf_bytes
    )
    document = ConsentimientoDocumentoFinal(
        tenant_id=tenant_id,
        consentimiento_id=row.id,
        s3_bucket=stored.bucket,
        s3_key=stored.key,
        s3_version_id=stored.version_id,
        s3_etag=stored.etag,
        contenido_sha256=stored.sha256,
        content_type="application/pdf",
        size_bytes=stored.size_bytes,
    )
    db.add(document)
    await db.flush()
    payload = _serialize(row, firmantes=firmantes, documento=document)
    payload["verification_url"] = verification_url
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
    firmantes, documento, revocacion = await _evidence_for_consent(db, consentimiento.id)
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
    payload = {
        **_serialize(
            consentimiento,
            firmantes=firmantes,
            documento=documento,
            revocacion=revocacion,
        ),
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
    if documento is not None:
        payload["documento_final"]["download_url"] = final_consent_download_url(
            key=documento.s3_key, version_id=documento.s3_version_id
        )
    return payload


@router.post("/{id}/revocar", status_code=201)
async def revocar_consentimiento(
    id: str,
    data: RevocacionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create an immutable revocation event without updating the signed consent."""
    from app.core.clinical_rollout import feature_enabled

    if not feature_enabled("consent_finalization"):
        raise HTTPException(
            status_code=503,
            detail={"code": "clinical_feature_not_active", "feature": "consent_finalization"},
        )
    tenant_id = _tenant_uuid(request)
    result = (
        await db.execute(
            select(Consentimiento, Tenant)
            .join(Tenant, Tenant.id == Consentimiento.tenant_id)
            .where(Consentimiento.id == uuid.UUID(id), Consentimiento.tenant_id == tenant_id)
            .with_for_update(of=Consentimiento)
        )
    ).first()
    if result is None:
        raise HTTPException(status_code=404, detail="Consentimiento no encontrado")
    consentimiento, tenant = result
    if not consentimiento.firmado_medico_en:
        raise HTTPException(status_code=400, detail="Sólo se puede revocar un documento firmado")
    firmantes, documento, existing = await _evidence_for_consent(db, consentimiento.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="El consentimiento ya fue revocado")

    actor = await get_credencial_para_firma(db, tenant)
    revocacion = ConsentimientoRevocacion(
        tenant_id=tenant_id,
        consentimiento_id=consentimiento.id,
        motivo=data.motivo.strip(),
        actor_nombre=actor.nombre,
        actor_tipo="medico",
        revocado_en=datetime.now(timezone.utc),
    )
    db.add(revocacion)

    token = None
    if consentimiento.verification_token_id:
        token = (
            await db.execute(
                select(VerificationToken).where(
                    VerificationToken.id == consentimiento.verification_token_id
                )
            )
        ).scalar_one_or_none()
    if token is None:
        token, _plain = await get_or_create_verification_token(
            db,
            tenant_id=tenant_id,
            resource_type="consentimiento",
            resource_id=consentimiento.id,
            public_metadata={
                "folio": f"CONS-{str(consentimiento.id)[:8].upper()}",
                "medico_nombre": consentimiento.medico_nombre,
                "medico_cedula": consentimiento.medico_cedula,
                "fecha_emision": consentimiento.firmado_medico_en.isoformat(),
                "hash": consentimiento.hash_contenido,
            },
        )
        consentimiento.verification_token_id = token.id
    token.status = "revoked"
    token.revoked_at = revocacion.revocado_en
    await db.flush()
    return _serialize(
        consentimiento,
        firmantes=firmantes,
        documento=documento,
        revocacion=revocacion,
    )
