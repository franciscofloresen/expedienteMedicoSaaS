"""Assembly of the «Descargar todo» export document (no HTTP logic here).

Every query filters by ``tenant_id`` explicitly even though RLS already scopes
the session — defense in depth for the most sensitive bulk read in the system.
Download URLs are presigned and short-lived; a file whose scan status is not
``available`` is listed with ``url = None`` and its real state, never a URL.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.clinical_file import ClinicalFile
from app.models.consentimiento import Consentimiento
from app.models.consentimiento_evidencia import (
    ConsentimientoDocumentoFinal,
    ConsentimientoFirmante,
    ConsentimientoRevocacion,
)
from app.models.encuentro import EncuentroClinico
from app.models.expediente import Expediente
from app.models.fotografia_clinica import FotografiaClinica
from app.models.nota import Nota
from app.models.nota_diagnostico import NotaDiagnostico
from app.models.paciente import Paciente
from app.models.procedimiento import EventoAdverso, ProcedimientoChecklist
from app.models.receta import Receta
from app.models.tenant import Tenant
from app.models.verification_token import VerificationToken
from app.schemas.exportacion import (
    ArchivoExport,
    ChecklistExport,
    ConsentimientoExport,
    ConsultorioExport,
    DiagnosticoExport,
    DocumentoFinalExport,
    EncuentroExport,
    EventoAdversoExport,
    ExpedienteExport,
    ExportacionExpediente,
    FirmaExport,
    FirmanteExport,
    FotografiaExport,
    IndiceConsultorioExport,
    IndicePacienteExport,
    NotaExport,
    PacienteExport,
    ProcedimientosExport,
    RecetaExport,
    RevocacionExport,
)
from app.services.clinical_storage import create_download_url
from app.services.consent_documents import final_consent_download_url
from app.services.encryption import decrypt_field
from app.services.verification import public_verification_url

# ClinicalFile rows that never appear in an export: reservations that were never
# completed, and files archived by the doctor (retained only for NOM-004).
_EXCLUDED_FILE_STATUSES = ("pending_upload", "expired")


def _parse_contenido(raw: str | None) -> dict[str, Any] | str | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    return parsed if isinstance(parsed, dict) else raw


async def _verification_urls(
    db: AsyncSession, tenant_id: uuid.UUID, token_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    if not token_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(VerificationToken).where(
                    VerificationToken.tenant_id == tenant_id,
                    VerificationToken.id.in_(token_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.id: public_verification_url(row.token) for row in rows}


def _firma(
    *,
    firmado: bool,
    hash_contenido: str | None,
    algoritmo: str | None,
    firmado_en: datetime | None,
    verification_token_id: uuid.UUID | None,
    urls: dict[uuid.UUID, str],
) -> FirmaExport:
    return FirmaExport(
        firmado=firmado,
        hash_contenido=hash_contenido,
        algoritmo=algoritmo if firmado else None,
        firmado_en=firmado_en,
        verification_url=urls.get(verification_token_id) if verification_token_id else None,
    )


async def _presigned_or_none(item: ClinicalFile) -> str | None:
    if item.status != "available":
        return None
    return await asyncio.to_thread(
        create_download_url,
        s3_key=item.s3_key,
        version_id=item.s3_version_id,
        filename=item.original_filename,
        content_type=item.content_type,
    )


async def _consultorio(db: AsyncSession, tenant_id: uuid.UUID) -> ConsultorioExport:
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        return ConsultorioExport(nombre_medico="")
    return ConsultorioExport(
        nombre_medico=tenant.nombre_medico,
        cedula=tenant.cedula,
        especialidad=tenant.especialidad,
    )


async def build_expediente_export(
    db: AsyncSession, *, tenant_id: uuid.UUID, expediente_id: uuid.UUID
) -> ExportacionExpediente | None:
    """Return the full export document, or None when the expediente is not visible."""
    row = (
        await db.execute(
            select(Expediente, Paciente)
            .join(Paciente, Expediente.paciente_id == Paciente.id)
            .where(
                Expediente.id == expediente_id,
                Expediente.tenant_id == tenant_id,
                Paciente.tenant_id == tenant_id,
            )
        )
    ).first()
    if row is None:
        return None
    expediente, paciente = row

    antecedentes = None
    if expediente.antecedentes_cifrado:
        antecedentes = decrypt_field(expediente.antecedentes_cifrado, str(tenant_id))

    encuentros = (
        (
            await db.execute(
                select(EncuentroClinico)
                .where(
                    EncuentroClinico.tenant_id == tenant_id,
                    EncuentroClinico.expediente_id == expediente.id,
                )
                .order_by(EncuentroClinico.creado_en)
            )
        )
        .scalars()
        .all()
    )

    notas = (
        (
            await db.execute(
                select(Nota)
                .where(Nota.tenant_id == tenant_id, Nota.expediente_id == expediente.id)
                .order_by(Nota.creado_en)
            )
        )
        .scalars()
        .all()
    )
    nota_ids = [nota.id for nota in notas]

    diagnosticos_by_nota: dict[uuid.UUID, list[NotaDiagnostico]] = {}
    recetas: list[Receta] = []
    if nota_ids:
        diag_rows = (
            (
                await db.execute(
                    select(NotaDiagnostico)
                    .where(
                        NotaDiagnostico.tenant_id == tenant_id,
                        NotaDiagnostico.nota_id.in_(nota_ids),
                    )
                    .order_by(NotaDiagnostico.orden)
                )
            )
            .scalars()
            .all()
        )
        for diag in diag_rows:
            diagnosticos_by_nota.setdefault(diag.nota_id, []).append(diag)
        recetas = list(
            (
                await db.execute(
                    select(Receta)
                    .where(Receta.tenant_id == tenant_id, Receta.nota_id.in_(nota_ids))
                    .order_by(Receta.creado_en)
                )
            )
            .scalars()
            .all()
        )

    consentimientos = (
        (
            await db.execute(
                select(Consentimiento)
                .where(
                    Consentimiento.tenant_id == tenant_id,
                    Consentimiento.expediente_id == expediente.id,
                )
                .order_by(Consentimiento.created_at)
            )
        )
        .scalars()
        .all()
    )
    consent_ids = [item.id for item in consentimientos]

    firmantes_by_consent: dict[uuid.UUID, list[ConsentimientoFirmante]] = {}
    revocacion_by_consent: dict[uuid.UUID, ConsentimientoRevocacion] = {}
    documentos: list[ConsentimientoDocumentoFinal] = []
    if consent_ids:
        firmante_rows = (
            (
                await db.execute(
                    select(ConsentimientoFirmante)
                    .where(
                        ConsentimientoFirmante.tenant_id == tenant_id,
                        ConsentimientoFirmante.consentimiento_id.in_(consent_ids),
                    )
                    .order_by(ConsentimientoFirmante.orden)
                )
            )
            .scalars()
            .all()
        )
        for firmante in firmante_rows:
            firmantes_by_consent.setdefault(firmante.consentimiento_id, []).append(firmante)
        revocaciones = (
            (
                await db.execute(
                    select(ConsentimientoRevocacion).where(
                        ConsentimientoRevocacion.tenant_id == tenant_id,
                        ConsentimientoRevocacion.consentimiento_id.in_(consent_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        revocacion_by_consent = {item.consentimiento_id: item for item in revocaciones}
        documentos = list(
            (
                await db.execute(
                    select(ConsentimientoDocumentoFinal)
                    .where(
                        ConsentimientoDocumentoFinal.tenant_id == tenant_id,
                        ConsentimientoDocumentoFinal.consentimiento_id.in_(consent_ids),
                    )
                    .order_by(ConsentimientoDocumentoFinal.creado_en)
                )
            )
            .scalars()
            .all()
        )

    checklists = (
        (
            await db.execute(
                select(ProcedimientoChecklist)
                .where(
                    ProcedimientoChecklist.tenant_id == tenant_id,
                    ProcedimientoChecklist.paciente_id == paciente.id,
                )
                .order_by(ProcedimientoChecklist.creado_en)
            )
        )
        .scalars()
        .all()
    )
    eventos = (
        (
            await db.execute(
                select(EventoAdverso)
                .where(
                    EventoAdverso.tenant_id == tenant_id,
                    EventoAdverso.paciente_id == paciente.id,
                )
                .order_by(EventoAdverso.creado_en)
            )
        )
        .scalars()
        .all()
    )

    archivos = (
        (
            await db.execute(
                select(ClinicalFile)
                .where(
                    ClinicalFile.tenant_id == tenant_id,
                    ClinicalFile.expediente_id == expediente.id,
                    ClinicalFile.deleted_at.is_(None),
                    ClinicalFile.status.notin_(_EXCLUDED_FILE_STATUSES),
                )
                .order_by(ClinicalFile.created_at)
            )
        )
        .scalars()
        .all()
    )

    foto_rows = (
        await db.execute(
            select(FotografiaClinica, ClinicalFile)
            .join(ClinicalFile, FotografiaClinica.clinical_file_id == ClinicalFile.id)
            .where(
                FotografiaClinica.tenant_id == tenant_id,
                ClinicalFile.tenant_id == tenant_id,
                FotografiaClinica.paciente_id == paciente.id,
                ClinicalFile.deleted_at.is_(None),
                ClinicalFile.status.notin_(_EXCLUDED_FILE_STATUSES),
            )
            .order_by(FotografiaClinica.creado_en)
        )
    ).all()

    token_ids: set[uuid.UUID] = set()
    for signed_items in (notas, recetas, consentimientos):
        for signed in signed_items:
            if signed.verification_token_id:
                token_ids.add(signed.verification_token_id)
    urls = await _verification_urls(db, tenant_id, token_ids)
    ttl = settings.file_signed_url_ttl_seconds

    notas_export = [
        NotaExport(
            id=str(nota.id),
            encuentro_clinico_id=str(nota.encuentro_clinico_id)
            if nota.encuentro_clinico_id
            else None,
            tipo_nota=nota.tipo_nota,
            estado=nota.estado,
            contenido=_parse_contenido(nota.contenido),
            motivo_consulta=nota.motivo_consulta,
            exploracion_fisica=nota.exploracion_fisica,
            plan_tratamiento=nota.plan_tratamiento,
            signos_vitales=nota.signos_vitales,
            diagnostico_cie10=nota.diagnostico_cie10,
            diagnosticos=[
                DiagnosticoExport(
                    cie10_code=diag.cie10_code,
                    descripcion=diag.descripcion_snapshot,
                    es_principal=diag.es_principal,
                    certeza=diag.certeza,
                    orden=diag.orden,
                )
                for diag in diagnosticos_by_nota.get(nota.id, [])
            ],
            medico_nombre=nota.medico_nombre,
            medico_cedula=nota.medico_cedula,
            medico_especialidad=nota.medico_especialidad,
            firma=_firma(
                firmado=bool(nota.firma_hash_contenido),
                hash_contenido=nota.firma_hash_contenido,
                algoritmo=nota.firma_algoritmo,
                firmado_en=nota.firmado_en,
                verification_token_id=nota.verification_token_id,
                urls=urls,
            ),
            creado_en=nota.creado_en,
        )
        for nota in notas
    ]

    recetas_export = [
        RecetaExport(
            id=str(receta.id),
            nota_id=str(receta.nota_id),
            medicamentos=receta.medicamentos or [],
            indicaciones_generales=receta.indicaciones_generales,
            medico_nombre=receta.medico_nombre,
            medico_cedula=receta.medico_cedula,
            medico_especialidad=receta.medico_especialidad,
            firma=_firma(
                firmado=bool(receta.firma_hash_contenido),
                hash_contenido=receta.firma_hash_contenido,
                algoritmo=receta.firma_algoritmo,
                firmado_en=receta.firmada_en,
                verification_token_id=receta.verification_token_id,
                urls=urls,
            ),
            creado_en=receta.creado_en,
        )
        for receta in recetas
    ]

    consentimientos_export = []
    for consent in consentimientos:
        revocacion = revocacion_by_consent.get(consent.id)
        consentimientos_export.append(
            ConsentimientoExport(
                id=str(consent.id),
                template_key=consent.template_key,
                version=consent.version,
                procedimiento=consent.procedimiento,
                status=consent.status,
                riesgos_principales=consent.riesgos_principales,
                contenido_renderizado=consent.contenido_renderizado,
                firmado_paciente_nombre=consent.firmado_paciente_nombre,
                firmado_paciente_en=consent.firmado_paciente_en,
                firmado_medico_en=consent.firmado_medico_en,
                medico_nombre=consent.medico_nombre,
                medico_cedula=consent.medico_cedula,
                medico_especialidad=consent.medico_especialidad,
                firmantes=[
                    FirmanteExport(
                        tipo=firmante.tipo,
                        orden=firmante.orden,
                        nombre=firmante.nombre,
                        relacion_paciente=firmante.relacion_paciente,
                        firma_sha256=firmante.firma_sha256,
                        firmado_en=firmante.firmado_en,
                    )
                    for firmante in firmantes_by_consent.get(consent.id, [])
                ],
                revocacion=RevocacionExport(
                    motivo=revocacion.motivo,
                    actor_nombre=revocacion.actor_nombre,
                    actor_tipo=revocacion.actor_tipo,
                    revocado_en=revocacion.revocado_en,
                )
                if revocacion
                else None,
                firma=_firma(
                    firmado=bool(consent.hash_contenido),
                    hash_contenido=consent.hash_contenido,
                    algoritmo=consent.firma_algoritmo,
                    firmado_en=consent.firmado_medico_en,
                    verification_token_id=consent.verification_token_id,
                    urls=urls,
                ),
                creado_en=consent.created_at,
            )
        )

    archivos_export = []
    for item in archivos:
        url = await _presigned_or_none(item)
        archivos_export.append(
            ArchivoExport(
                id=str(item.id),
                nombre_original=item.original_filename,
                content_type=item.content_type,
                tamano_bytes=item.size_bytes,
                categoria=item.category,
                creado_en=item.created_at,
                estado=item.status,
                url=url,
                url_expira_en=ttl if url else None,
            )
        )

    fotografias_export = []
    for foto, archivo in foto_rows:
        url = await _presigned_or_none(archivo)
        fotografias_export.append(
            FotografiaExport(
                id=str(foto.id),
                clinical_file_id=str(foto.clinical_file_id),
                consentimiento_id=str(foto.consentimiento_id) if foto.consentimiento_id else None,
                categoria=foto.categoria,
                lateralidad=foto.lateralidad,
                zona_anatomica=foto.zona_anatomica,
                fecha_toma=foto.fecha_toma,
                grupo_comparacion=foto.grupo_comparacion,
                nombre_original=archivo.original_filename,
                content_type=archivo.content_type,
                tamano_bytes=archivo.size_bytes,
                estado=archivo.status,
                url=url,
                url_expira_en=ttl if url else None,
            )
        )

    documentos_export = []
    for documento in documentos:
        url = await asyncio.to_thread(
            final_consent_download_url,
            key=documento.s3_key,
            version_id=documento.s3_version_id,
        )
        documentos_export.append(
            DocumentoFinalExport(
                consentimiento_id=str(documento.consentimiento_id),
                content_type=documento.content_type,
                tamano_bytes=documento.size_bytes,
                contenido_sha256=documento.contenido_sha256,
                creado_en=documento.creado_en,
                url=url,
                url_expira_en=ttl if url else None,
            )
        )

    return ExportacionExpediente(
        generado_en=datetime.now(timezone.utc),
        consultorio=await _consultorio(db, tenant_id),
        paciente=PacienteExport(
            id=str(paciente.id),
            nombre_completo=paciente.nombre_completo,
            fecha_nacimiento=paciente.fecha_nacimiento,
            sexo=paciente.sexo,
            curp=paciente.curp,
            entidad_nacimiento=paciente.entidad_nacimiento,
            nacionalidad=paciente.nacionalidad,
            ocupacion=paciente.ocupacion,
            telefono=paciente.telefono,
            email=paciente.email,
            aseguradora=paciente.aseguradora,
            num_poliza=paciente.num_poliza,
            contacto_emergencia=paciente.contacto_emergencia,
            telefono_emergencia=paciente.telefono_emergencia,
            tipo_sangre=paciente.tipo_sangre,
            alergias=paciente.alergias,
            creado_en=paciente.creado_en,
        ),
        expediente=ExpedienteExport(
            id=str(expediente.id),
            folio=expediente.folio,
            estado=expediente.estado,
            antecedentes=antecedentes,
            creado_en=expediente.creado_en,
        ),
        encuentros=[
            EncuentroExport(
                id=str(item.id),
                cita_id=str(item.cita_id) if item.cita_id else None,
                tipo=item.tipo,
                estado=item.estado,
                clasificacion_origen=item.clasificacion_origen,
                nota_inicial_id=str(item.nota_inicial_id) if item.nota_inicial_id else None,
                fecha_inicio=item.fecha_inicio,
                fecha_fin=item.fecha_fin,
                creado_en=item.creado_en,
            )
            for item in encuentros
        ],
        notas=notas_export,
        recetas=recetas_export,
        consentimientos=consentimientos_export,
        procedimientos=ProcedimientosExport(
            checklists=[
                ChecklistExport(
                    id=str(item.id),
                    encuentro_id=str(item.encuentro_id) if item.encuentro_id else None,
                    momento=item.momento,
                    items=item.items or [],
                    observaciones=item.observaciones,
                    creado_en=item.creado_en,
                    modificado_en=item.modificado_en,
                )
                for item in checklists
            ],
            eventos_adversos=[
                EventoAdversoExport(
                    id=str(item.id),
                    encuentro_id=str(item.encuentro_id) if item.encuentro_id else None,
                    descripcion=item.descripcion,
                    severidad=item.severidad,
                    fecha=item.fecha,
                    manejo=item.manejo,
                    estado=item.estado,
                    creado_en=item.creado_en,
                    modificado_en=item.modificado_en,
                )
                for item in eventos
            ],
        ),
        archivos=archivos_export,
        fotografias=fotografias_export,
        documentos_finales=documentos_export,
    )


async def build_consultorio_index(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    cursor: uuid.UUID | None = None,
    limit: int = 500,
) -> IndiceConsultorioExport:
    """Index of every expediente in the tenant — no binaries, no clinical content.

    Keyset-paginated by expediente id so a consultorio with more than ``limit``
    patients pages instead of attempting a single giant response.
    """
    stmt = (
        select(Expediente, Paciente)
        .join(Paciente, Expediente.paciente_id == Paciente.id)
        .where(Expediente.tenant_id == tenant_id, Paciente.tenant_id == tenant_id)
        .order_by(Expediente.id)
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(Expediente.id > cursor)
    rows = (await db.execute(stmt)).all()

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = str(rows[-1][0].id)

    expediente_ids = [expediente.id for expediente, _ in rows]
    paciente_ids = [paciente.id for _, paciente in rows]

    async def _counts_by(
        column: Any, model: Any, ids: list[uuid.UUID], *extra: Any
    ) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        result = await db.execute(
            select(column, func.count())
            .where(model.tenant_id == tenant_id, column.in_(ids), *extra)
            .group_by(column)
        )
        return {row[0]: row[1] for row in result.all()}

    notas_counts = await _counts_by(Nota.expediente_id, Nota, expediente_ids)
    encuentros_counts = await _counts_by(
        EncuentroClinico.expediente_id, EncuentroClinico, expediente_ids
    )
    consent_counts = await _counts_by(
        Consentimiento.expediente_id, Consentimiento, expediente_ids
    )
    archivos_counts = await _counts_by(
        ClinicalFile.expediente_id,
        ClinicalFile,
        expediente_ids,
        ClinicalFile.deleted_at.is_(None),
        ClinicalFile.status.notin_(_EXCLUDED_FILE_STATUSES),
    )
    fotos_counts = await _counts_by(
        FotografiaClinica.paciente_id, FotografiaClinica, paciente_ids
    )

    recetas_counts: dict[uuid.UUID, int] = {}
    if expediente_ids:
        receta_rows = await db.execute(
            select(Nota.expediente_id, func.count())
            .select_from(Receta)
            .join(Nota, Receta.nota_id == Nota.id)
            .where(
                Receta.tenant_id == tenant_id,
                Nota.tenant_id == tenant_id,
                Nota.expediente_id.in_(expediente_ids),
            )
            .group_by(Nota.expediente_id)
        )
        recetas_counts = {row[0]: row[1] for row in receta_rows.all()}

    return IndiceConsultorioExport(
        generado_en=datetime.now(timezone.utc),
        consultorio=await _consultorio(db, tenant_id),
        pacientes=[
            IndicePacienteExport(
                paciente_id=str(paciente.id),
                nombre_completo=paciente.nombre_completo,
                expediente_id=str(expediente.id),
                folio=expediente.folio,
                conteos={
                    "encuentros": encuentros_counts.get(expediente.id, 0),
                    "notas": notas_counts.get(expediente.id, 0),
                    "recetas": recetas_counts.get(expediente.id, 0),
                    "consentimientos": consent_counts.get(expediente.id, 0),
                    "archivos": archivos_counts.get(expediente.id, 0),
                    "fotografias": fotos_counts.get(paciente.id, 0),
                },
                exportacion_url=f"/api/v1/expedientes/{expediente.id}/exportacion",
            )
            for expediente, paciente in rows
        ],
        next_cursor=next_cursor,
    )
