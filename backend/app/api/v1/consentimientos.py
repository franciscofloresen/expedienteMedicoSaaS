import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.consentimiento import Consentimiento
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from app.models.tenant import Tenant
from app.services.credenciales import CredencialFirma, get_credencial_para_firma
from app.services.firma import sign_note
from app.services.verification import (
    get_or_create_verification_token,
    public_verification_url,
)

router = APIRouter()

TEMPLATES: dict[str, dict[str, str]] = {
    "general_atencion": {
        "nombre": "Consentimiento general de atención médica",
        "version": "1.0",
        "descripcion": (
            "Autorización para valoración clínica, exploración física e indicación de estudios "
            "o tratamiento conforme al criterio del médico tratante."
        ),
        "beneficios": "Diagnóstico oportuno, plan de manejo personalizado y seguimiento del padecimiento.",
        "alternativas": "No recibir atención, solicitar una segunda opinión o ser referido a otra unidad médica.",
        "cuidados": "Seguir las indicaciones entregadas, acudir a las citas de control y reportar cualquier dato de alarma.",
        "riesgos": "Molestias propias de la exploración, reacciones no previstas y necesidad de estudios o referencia.",
    },
    "estetico_no_quirurgico": {
        "nombre": "Procedimiento estético no quirúrgico",
        "version": "1.0",
        "descripcion": (
            "Procedimiento estético sin cirugía (peelings, aparatología o tratamientos faciales) "
            "cuyo resultado depende de la respuesta individual de cada paciente."
        ),
        "beneficios": "Mejoría del aspecto de la piel o de la zona tratada, sin tiempos de recuperación quirúrgicos.",
        "alternativas": "Otros tratamientos estéticos, manejo quirúrgico o no realizar el procedimiento.",
        "cuidados": "Evitar sol directo, usar protector solar, seguir la rutina indicada y no manipular la zona tratada.",
        "riesgos": "Inflamación, dolor, equimosis, asimetría, infección, reacción alérgica o resultado distinto al esperado.",
    },
    "toxina_botulinica": {
        "nombre": "Aplicación de toxina botulínica",
        "version": "1.0",
        "descripcion": (
            "Aplicación de toxina botulínica tipo A mediante microinyecciones para relajar músculos "
            "y atenuar arrugas de expresión. El efecto es temporal (aprox. 3 a 6 meses)."
        ),
        "beneficios": "Suavizado de líneas de expresión y prevención de arrugas dinámicas.",
        "alternativas": "Rellenos, tratamientos con aparatología o no aplicar la toxina.",
        "cuidados": "No agacharse ni hacer ejercicio intenso las primeras horas, no masajear la zona y mantenerse erguido.",
        "riesgos": "Dolor, equimosis, cefalea, asimetría, ptosis temporal, reacción local o necesidad de retoque.",
    },
    "relleno_acido_hialuronico": {
        "nombre": "Relleno con ácido hialurónico",
        "version": "1.0",
        "descripcion": (
            "Aplicación de ácido hialurónico para dar volumen, hidratar o corregir contornos "
            "faciales. Es reabsorbible y su duración varía según la zona y el producto."
        ),
        "beneficios": "Restauración de volumen, hidratación y armonización de los rasgos faciales.",
        "alternativas": "Toxina botulínica, bioestimuladores, procedimientos quirúrgicos o no realizar el relleno.",
        "cuidados": "Aplicar frío si se indica, evitar calor extremo y ejercicio intenso, y no presionar la zona tratada.",
        "riesgos": "Inflamación, equimosis, nódulos, asimetría, infección, compromiso vascular y necesidad de disolución.",
    },
    "dermatologico": {
        "nombre": "Tratamiento dermatológico",
        "version": "1.0",
        "descripcion": (
            "Indicación de tratamiento dermatológico (tópico, oral o en consultorio) para el manejo "
            "de la condición de piel diagnosticada, con seguimiento por el médico tratante."
        ),
        "beneficios": "Control de la enfermedad cutánea, mejoría de los síntomas y del aspecto de la piel.",
        "alternativas": "Otros esquemas terapéuticos, manejo expectante o una segunda opinión dermatológica.",
        "cuidados": "Aplicar los productos según indicación, usar protector solar y reportar irritación o falta de mejoría.",
        "riesgos": "Irritación, ardor, resequedad, manchas, reacción alérgica, falta de respuesta o recaída.",
    },
}


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


def _render_content(
    *,
    template: dict[str, str],
    paciente: Paciente,
    credencial: CredencialFirma,
    procedimiento: str,
    riesgos: str,
) -> str:
    return (
        f"{template['nombre']}\n\n"
        f"Paciente: {paciente.nombre_completo}\n"
        f"Procedimiento: {procedimiento}\n"
        f"Médico: {credencial.nombre}\n"
        f"Cédula profesional: {credencial.cedula}\n"
        f"Fecha: {datetime.now(timezone.utc).date().isoformat()}\n\n"
        f"Descripción del procedimiento:\n{template['descripcion']}\n\n"
        f"Beneficios esperados:\n{template['beneficios']}\n\n"
        f"Alternativas:\n{template['alternativas']}\n\n"
        f"Riesgos principales:\n{riesgos}\n\n"
        f"Cuidados posteriores:\n{template['cuidados']}\n\n"
        "El paciente declara haber recibido información suficiente sobre el procedimiento, "
        "sus beneficios, alternativas y cuidados posteriores, que resolvió sus dudas y que "
        "ningún resultado médico o estético puede garantizarse.\n\n"
        "CloudMedRecord ayuda a documentar y generar evidencia verificable; este formato no "
        "sustituye asesoría legal ni el criterio clínico del médico tratante."
    )


def _serialize(row: Consentimiento) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "paciente_id": str(row.paciente_id),
        "expediente_id": str(row.expediente_id),
        "template_key": row.template_key,
        "version": row.version,
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
async def templates() -> Any:
    return [
        {
            "key": key,
            "nombre": value["nombre"],
            "version": value["version"],
            "descripcion": value["descripcion"],
            "riesgos": value["riesgos"],
        }
        for key, value in TEMPLATES.items()
    ]


@router.post("", status_code=201)
async def create_consentimiento(
    data: ConsentimientoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    tenant_id = _tenant_uuid(request)
    template = TEMPLATES.get(data.template_key)
    if not template:
        raise HTTPException(status_code=400, detail="Plantilla de consentimiento inválida")

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
        procedimiento=data.procedimiento,
        riesgos_principales=riesgos,
        contenido_renderizado=_render_content(
            template=template,
            paciente=paciente,
            credencial=credencial,
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
