"""API v1 — Notas Médicas y Firmas Digitales (NOM-004 §6)."""

import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_reauthentication
from app.db.session import get_db
from app.models.expediente import Expediente
from app.models.nota import Nota
from app.models.nota_diagnostico import NotaDiagnostico
from app.models.paciente import Paciente
from app.services.credenciales import get_credencial_para_firma
from app.services.diagnosticos import (
    DiagnosticoInput,
    DiagnosticoInvalidoError,
    crear_diagnosticos_para_nota,
)
from app.services.firma import sign_note, verify_signature
from app.services.verification import (
    get_or_create_verification_token,
    public_verification_url,
)

logger = logging.getLogger("medrecord")

router = APIRouter()


def _tenant_uuid(request: Request) -> UUID:
    return UUID(str(request.state.tenant_id))


def _signature_preview(signature: bytes | str | None) -> str | None:
    if not signature:
        return None
    if isinstance(signature, bytes):
        return signature.hex()[:32]
    return signature[:32]


def _serialize_diagnostico(diagnostico: NotaDiagnostico) -> dict[str, Any]:
    return {
        "code": diagnostico.cie10_code,
        "description": diagnostico.descripcion_snapshot,
        "catalog_version": diagnostico.version_snapshot,
        "es_principal": diagnostico.es_principal,
        "certeza": diagnostico.certeza,
        "orden": diagnostico.orden,
    }


async def _diagnosticos_por_nota(
    db: AsyncSession, nota_ids: list[UUID]
) -> dict[UUID, list[dict[str, Any]]]:
    if not nota_ids:
        return {}
    rows = (
        await db.execute(
            select(NotaDiagnostico)
            .where(NotaDiagnostico.nota_id.in_(nota_ids))
            .order_by(NotaDiagnostico.nota_id, NotaDiagnostico.orden, NotaDiagnostico.creado_en)
        )
    ).scalars()
    grouped: dict[UUID, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.nota_id, []).append(_serialize_diagnostico(row))
    return grouped


async def _build_legal_note_payload(
    nota_id: UUID,
    request: Request,
    db: AsyncSession,
) -> dict[str, Any]:
    tenant_id = _tenant_uuid(request)
    stmt = (
        select(Nota, Expediente, Paciente)
        .join(Expediente, Nota.expediente_id == Expediente.id)
        .join(Paciente, Expediente.paciente_id == Paciente.id)
        .where(Nota.id == nota_id, Nota.tenant_id == tenant_id)
    )
    row = (await db.execute(stmt)).first()
    if not row:
        raise HTTPException(status_code=404, detail="Nota no encontrada")

    nota, expediente, paciente = row
    if not nota.firma_digital or not nota.firma_hash_contenido:
        raise HTTPException(
            status_code=400, detail="La nota debe estar firmada para generar el documento legal"
        )

    # This is a read/render path (GET legal-preview & print) over an already-signed,
    # immutable note. Do NOT write back nota.verification_token_id: the note is locked
    # by the NOM-004 trigger (any UPDATE with es_editable=false raises), and the token
    # is always discoverable via verification_tokens.resource_id, so the FK backfill is
    # redundant. Signing already links the token on the note.
    _token_row, plain_token = await get_or_create_verification_token(
        db,
        tenant_id=tenant_id,
        resource_type="nota",
        resource_id=nota.id,
        public_metadata={
            "folio": f"NOTA-{str(nota.id)[:8].upper()}",
            "medico_nombre": nota.medico_nombre,
            "medico_cedula": nota.medico_cedula,
            "fecha_emision": nota.firmado_en.isoformat() if nota.firmado_en else None,
            "hash": nota.firma_hash_contenido,
        },
    )
    verification_url = public_verification_url(plain_token)

    diagnosticos_cie10 = (await _diagnosticos_por_nota(db, [nota.id])).get(nota.id, [])

    return {
        "id": str(nota.id),
        "folio": f"NOTA-{str(nota.id)[:8].upper()}",
        "tipo_documento": "nota",
        "tipo_nota": nota.tipo_nota,
        "paciente": {
            "nombre_completo": paciente.nombre_completo,
            "fecha_nacimiento": paciente.fecha_nacimiento.isoformat(),
            "sexo": paciente.sexo,
        },
        "expediente": {"id": str(expediente.id), "folio": expediente.folio},
        "medico": {
            "nombre": nota.medico_nombre,
            "cedula": nota.medico_cedula,
            "especialidad": nota.medico_especialidad,
        },
        "fechas": {
            "creado_en": nota.creado_en.isoformat(),
            "firmado_en": nota.firmado_en.isoformat() if nota.firmado_en else None,
        },
        "contenido": json.loads(nota.contenido) if nota.contenido else {},
        "motivo_consulta": nota.motivo_consulta,
        "exploracion_fisica": nota.exploracion_fisica,
        "plan_tratamiento": nota.plan_tratamiento,
        "diagnostico_cie10": nota.diagnostico_cie10,
        "diagnosticos_cie10": diagnosticos_cie10,
        "signos_vitales": nota.signos_vitales or {},
        "firma": {
            "hash": nota.firma_hash_contenido,
            "algoritmo": nota.firma_algoritmo,
            "firma_abreviada": _signature_preview(nota.firma_digital),
            "verification_url": verification_url,
        },
        "leyenda": (
            "Documento firmado digitalmente dentro de CloudMedRecord. "
            "El QR permite verificar metadatos mínimos e integridad sin exponer contenido clínico sensible."
        ),
    }


class DiagnosticoCie10Input(BaseModel):
    """One structured CIE-10 diagnosis for a note (Fase 3). Written create-only (§1.1)."""

    code: str
    es_principal: bool = False
    certeza: str = "presuntivo"
    orden: int | None = None


class NotaCreate(BaseModel):
    expediente_id: UUID
    # Fase 2: optional link to the clinical encounter. Written ONLY here, at creation
    # — never UPDATEd onto a signed nota (§1.1). Historical notes stay unlinked.
    encuentro_clinico_id: UUID | None = None
    tipo_nota: str = Field(..., description="evolucion, interconsulta, ingreso, egreso")
    contenido: dict[str, Any]
    signos_vitales: dict[str, Any] = Field(default_factory=dict)
    diagnosticos: list[str] = Field(default_factory=list)
    # Fase 3: structured, coded diagnoses. Optional & defaulted → backward compatible.
    # Written create-only alongside the note; the free-text ``diagnostico_cie10`` below is
    # kept as legacy evidence.
    diagnosticos_cie10: list[DiagnosticoCie10Input] = Field(default_factory=list)
    tratamiento: str | None = None
    diagnostico_cie10: str | None = None
    motivo_consulta: str | None = None
    exploracion_fisica: str | None = None
    plan_tratamiento: str | None = None

    @model_validator(mode="after")
    def validate_nom004_compliance(self) -> "NotaCreate":
        if self.tipo_nota not in ("evolucion", "interconsulta", "ingreso", "egreso"):
            raise ValueError("Tipo de nota inválido según la NOM-004")
        if self.tipo_nota in ("evolucion", "ingreso", "egreso") and not self.signos_vitales:
            raise ValueError(
                f"Los signos vitales son obligatorios para notas de {self.tipo_nota} (NOM-004)"
            )
        if self.tipo_nota == "evolucion" and not self.diagnosticos:
            raise ValueError("El diagnóstico es obligatorio para notas de evolución (NOM-004)")
        return self


class NotaUpdate(BaseModel):
    contenido: dict[str, Any] | None = None
    signos_vitales: dict[str, Any] | None = None
    diagnosticos: list[str] | None = None
    tratamiento: str | None = None
    diagnostico_cie10: str | None = None
    motivo_consulta: str | None = None
    exploracion_fisica: str | None = None
    plan_tratamiento: str | None = None


@router.get("/")
async def list_notas(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> Any:
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
) -> Any:
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

    # Validation is deferred to the frontend or simplified rules later.

    # Serialize all clinical content into the `contenido` Text column
    contenido_completo = json.dumps(
        {
            **data.contenido,
            "diagnosticos": data.diagnosticos,
            "tratamiento": data.tratamiento,
        },
        ensure_ascii=False,
    )

    nota = Nota(
        tenant_id=tenant_id,
        expediente_id=str(data.expediente_id),
        encuentro_clinico_id=data.encuentro_clinico_id,
        tipo_nota=data.tipo_nota,
        contenido=contenido_completo,
        signos_vitales=data.signos_vitales,
        diagnostico_cie10=data.diagnostico_cie10,
        motivo_consulta=data.motivo_consulta,
        exploracion_fisica=data.exploracion_fisica,
        plan_tratamiento=data.plan_tratamiento,
        estado="draft",
        creado_por=tenant_id,
        es_editable=True,
    )
    db.add(nota)
    await db.flush()

    # Fase 3: attach structured CIE-10 diagnoses at creation (create-only, §1.1). The note
    # is never UPDATEd for this — the diagnoses point at it.
    if data.diagnosticos_cie10:
        from app.core.clinical_rollout import feature_enabled

        if not feature_enabled("structured_diagnoses"):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "clinical_feature_not_active",
                    "feature": "structured_diagnoses",
                },
            )
        try:
            diagnosticos_creados = await crear_diagnosticos_para_nota(
                db,
                tenant_id=tenant_id,
                nota_id=nota.id,
                diagnosticos=[
                    DiagnosticoInput(
                        code=d.code,
                        es_principal=d.es_principal,
                        certeza=d.certeza,
                        orden=d.orden,
                    )
                    for d in data.diagnosticos_cie10
                ],
                creado_por=tenant_id,
            )
            # Keep the structured snapshots inside the note's canonical JSON as well.
            # The note is still a draft here, so this remains create-time data and is
            # subsequently covered by the existing signature payload.
            contenido_con_cie10 = json.loads(nota.contenido)
            contenido_con_cie10["diagnosticos_cie10"] = [
                _serialize_diagnostico(d) for d in diagnosticos_creados
            ]
            nota.contenido = json.dumps(contenido_con_cie10, ensure_ascii=False)
            await db.flush()
        except DiagnosticoInvalidoError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"id": str(nota.id), "status": "creada, pendiente de firma"}


@router.put("/{nota_id}")
async def update_nota(
    nota_id: UUID,
    data: NotaUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
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
            "Según la NOM-004, las correcciones deben realizarse como notas de adenda.",
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

    if data.motivo_consulta is not None:
        nota.motivo_consulta = data.motivo_consulta
    if data.exploracion_fisica is not None:
        nota.exploracion_fisica = data.exploracion_fisica
    if data.plan_tratamiento is not None:
        nota.plan_tratamiento = data.plan_tratamiento

    await db.flush()

    return {"id": str(nota.id), "status": "actualizada"}


@router.get("/expediente/{expediente_id}")
async def list_notas_by_expediente(
    expediente_id: UUID,
    request: Request,
    limit: int | None = Query(default=None, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Lista todas las notas de un expediente, ordenadas por fecha."""
    stmt = (
        select(Nota)
        .where(Nota.expediente_id == expediente_id)
        .order_by(Nota.creado_en.desc(), Nota.id.desc())
    )
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    notas = result.scalars().all()
    diagnosticos_por_nota = await _diagnosticos_por_nota(db, [n.id for n in notas])

    return [
        {
            "id": str(n.id),
            "tipo_nota": n.tipo_nota,
            "contenido": json.loads(n.contenido) if n.contenido else {},
            "signos_vitales": n.signos_vitales,
            "motivo_consulta": n.motivo_consulta,
            "exploracion_fisica": n.exploracion_fisica,
            "plan_tratamiento": n.plan_tratamiento,
            "diagnostico_cie10": n.diagnostico_cie10,
            "diagnosticos_cie10": diagnosticos_por_nota.get(n.id, []),
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
    nota_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _reauthenticated: None = Depends(require_reauthentication),
) -> Any:
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
    content_to_sign = json.dumps(
        {
            "id": str(nota.id),
            "expediente_id": str(nota.expediente_id),
            "tipo_nota": nota.tipo_nota,
            "motivo_consulta": nota.motivo_consulta,
            "exploracion_fisica": nota.exploracion_fisica,
            "plan_tratamiento": nota.plan_tratamiento,
            "diagnostico_cie10": nota.diagnostico_cie10,
            "contenido": contenido_dict,
            "signos_vitales": nota.signos_vitales,
            "creado_en": nota.creado_en.isoformat(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

    # Pull doctor identity directly from the database for strict legal compliance (NOM-004)
    from app.models.tenant import Tenant

    stmt_tenant = select(Tenant).where(Tenant.id == tenant_id)
    tenant_row = (await db.execute(stmt_tenant)).scalar_one_or_none()

    if not tenant_row:
        raise HTTPException(
            status_code=403,
            detail="No se encontró el perfil médico asociado para firmar la nota.",
        )

    credencial = await get_credencial_para_firma(db, tenant_row)
    medico_nombre = credencial.nombre
    medico_cedula = credencial.cedula

    if not medico_cedula or not medico_cedula.strip():
        raise HTTPException(status_code=400, detail="Cédula profesional requerida para firmar")

    medico_especialidad = credencial.especialidad

    # Only the KMS/signing call is guarded as "servicio de firma no disponible".
    # DB persistence and the verification token are handled separately so their
    # errors are not masked as a signing-service outage.
    try:
        signature_data = sign_note(
            content=content_to_sign,
            tenant_id=tenant_id,
            nota_id=str(nota_id),
            medico_nombre=medico_nombre,
            medico_cedula=medico_cedula,
            medico_especialidad=medico_especialidad,
        )
    except Exception as e:
        logger.warning("Signing failed for nota %s: %s", nota_id, e)
        raise HTTPException(
            status_code=503,
            detail="El servicio de firma digital no está disponible en este entorno.",
        ) from e

    # Create the verification token FIRST, while the note is still editable.
    #
    # The `notas_signed_immutable` trigger raises whenever a note whose
    # es_editable is already false is UPDATEd. So signing must touch the notas
    # row exactly once: any second UPDATE (e.g. to attach verification_token_id)
    # after es_editable flips to false is rejected as a NOM-004 violation. We
    # therefore mint the token now — it only INSERTs into verification_tokens,
    # never touches notas — and fold its id into the single signing UPDATE below.
    #
    # Token/QR remains best-effort: wrapped in a savepoint so any failure rolls
    # back only the token and still lets the note be signed without one.
    firmado_en = signature_data["firmado_en"]
    verification_url = None
    verification_token_id = None
    try:
        async with db.begin_nested():
            token_row, plain_token = await get_or_create_verification_token(
                db,
                tenant_id=UUID(str(tenant_id)),
                resource_type="nota",
                resource_id=nota.id,
                public_metadata={
                    "folio": f"NOTA-{str(nota.id)[:8].upper()}",
                    "medico_nombre": signature_data["medico_nombre"],
                    "medico_cedula": signature_data["medico_cedula"],
                    "fecha_emision": firmado_en.isoformat() if firmado_en else None,
                    "hash": signature_data["firma_hash_contenido"],
                },
            )
        verification_token_id = token_row.id
        verification_url = public_verification_url(plain_token)
    except Exception as e:
        logger.error(
            "Verification token creation failed for nota %s: %s", nota.id, e, exc_info=True
        )
        verification_token_id = None
        verification_url = None

    # Persist ALL signature metadata (9 fields) + the token link + the immutable
    # lock in a SINGLE UPDATE. es_editable is still true at this point, so the
    # NOM-004 trigger allows the write; there is no second UPDATE afterwards.
    nota.firma_digital = signature_data["firma_digital"]
    nota.firma_hash_contenido = signature_data["firma_hash_contenido"]
    nota.firma_kms_key_id = signature_data["firma_kms_key_id"]
    nota.firma_algoritmo = signature_data["firma_algoritmo"]
    nota.firmado_en = firmado_en
    nota.firmado_por = tenant_id
    nota.medico_nombre = signature_data["medico_nombre"]
    nota.medico_cedula = signature_data["medico_cedula"]
    nota.medico_especialidad = signature_data["medico_especialidad"]
    nota.verification_token_id = verification_token_id

    # Lock the note — NOM-004: signed notes are immutable
    nota.es_editable = False
    nota.estado = "signed"

    # Fase 12 §9 (Fase 2 debt): stamp the signing credential on the ENCUENTRO, not
    # the note. The signed note is never UPDATEd again (§1.1); the link travels on
    # the mutable encuentro side. Set once, when still NULL, so a correction never
    # rewrites which credential signed the encounter's note.
    if nota.encuentro_clinico_id and credencial.credencial_id:
        from app.models.encuentro import EncuentroClinico

        encuentro = (
            await db.execute(
                select(EncuentroClinico).where(
                    EncuentroClinico.id == nota.encuentro_clinico_id
                )
            )
        ).scalar_one_or_none()
        if encuentro is not None and encuentro.credencial_id is None:
            encuentro.credencial_id = credencial.credencial_id

    await db.flush()

    return {
        "id": str(nota.id),
        "firmada": True,
        "firma_hash_contenido": nota.firma_hash_contenido,
        "firmado_en": nota.firmado_en.isoformat(),
        "medico_nombre": nota.medico_nombre,
        "medico_cedula": nota.medico_cedula,
        "es_editable": False,
        "verification_url": verification_url,
    }


@router.get("/{nota_id}/verificar-firma")
async def verificar_firma(
    nota_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
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
    content_to_verify = json.dumps(
        {
            "id": str(nota.id),
            "expediente_id": str(nota.expediente_id),
            "tipo_nota": nota.tipo_nota,
            "motivo_consulta": nota.motivo_consulta,
            "exploracion_fisica": nota.exploracion_fisica,
            "plan_tratamiento": nota.plan_tratamiento,
            "diagnostico_cie10": nota.diagnostico_cie10,
            "contenido": contenido_dict,
            "signos_vitales": nota.signos_vitales,
            "creado_en": nota.creado_en.isoformat(),
        },
        ensure_ascii=False,
        sort_keys=True,
    )

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


@router.get("/{nota_id}/legal-preview")
async def legal_preview_nota(
    nota_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await _build_legal_note_payload(nota_id, request, db)


@router.get("/{nota_id}/print")
async def print_nota(
    nota_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await _build_legal_note_payload(nota_id, request, db)
