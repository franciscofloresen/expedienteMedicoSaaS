"""Seed local beta demo data.

Usage:
    cd backend
    python -m scripts.seed_beta_demo
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import _get_session_factory
from app.models.audit_log import AuditLog
from app.models.cita import Cita
from app.models.expediente import Expediente
from app.models.nota import Nota
from app.models.paciente import Paciente
from app.models.receta import Receta
from app.models.tenant import Tenant
from app.services.firma import sign_note


async def main() -> None:
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            tenant = (
                await session.execute(
                    select(Tenant).where(Tenant.email == "demo@cloudmedrecord.mx")
                )
            ).scalar_one_or_none()
            if not tenant:
                tenant = Tenant(
                    nombre_medico="Dra. Valeria Torres",
                    cedula="DEMO123456",
                    especialidad="Dermatologia estetica",
                    email="demo@cloudmedrecord.mx",
                    plan="beta_fundador",
                    terms_accepted_at=datetime.now(UTC),
                    terms_version="beta-2026",
                )
                session.add(tenant)
                await session.flush()

            paciente = (
                await session.execute(
                    select(Paciente).where(
                        Paciente.tenant_id == tenant.id,
                        Paciente.email == "paciente.demo@example.com",
                    )
                )
            ).scalar_one_or_none()
            if not paciente:
                paciente = Paciente(
                    tenant_id=tenant.id,
                    nombre_completo="Mariana Lopez Demo",
                    fecha_nacimiento=datetime(1991, 4, 12).date(),
                    sexo="F",
                    telefono="523121940941",
                    email="paciente.demo@example.com",
                    alergias="Niega alergias medicamentosas conocidas",
                    tipo_sangre="O+",
                    creado_por=tenant.id,
                )
                session.add(paciente)
                await session.flush()

            expediente = Expediente(
                tenant_id=tenant.id,
                paciente_id=paciente.id,
                folio=f"DEMO-{str(paciente.id)[:6].upper()}",
                creado_por=tenant.id,
                estado="activo",
            )
            session.add(expediente)
            await session.flush()

            signed_content = {
                "diagnosticos": ["Ritides dinamicas tercio superior"],
                "tratamiento": "Plan de aplicacion de toxina botulinica posterior a consentimiento.",
            }
            signed_note = Nota(
                tenant_id=tenant.id,
                expediente_id=expediente.id,
                tipo_nota="evolucion",
                contenido=json.dumps(signed_content, ensure_ascii=False),
                signos_vitales={"frecuencia_cardiaca": 72, "frecuencia_respiratoria": 16, "temperatura": 36.5, "tension_arterial": "118/76"},
                diagnostico_cie10="L98.8",
                motivo_consulta="Valoracion para procedimiento estetico no quirurgico.",
                exploracion_fisica="Paciente alerta, piel integra, sin lesiones activas en zona de aplicacion.",
                plan_tratamiento=signed_content["tratamiento"],
                creado_por=tenant.id,
                estado="draft",
                es_editable=True,
            )
            session.add(signed_note)
            await session.flush()
            payload = json.dumps(
                {
                    "id": str(signed_note.id),
                    "expediente_id": str(expediente.id),
                    "tipo_nota": signed_note.tipo_nota,
                    "motivo_consulta": signed_note.motivo_consulta,
                    "exploracion_fisica": signed_note.exploracion_fisica,
                    "plan_tratamiento": signed_note.plan_tratamiento,
                    "diagnostico_cie10": signed_note.diagnostico_cie10,
                    "contenido": signed_content,
                    "signos_vitales": signed_note.signos_vitales,
                    "creado_en": signed_note.creado_en.isoformat(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            signature = sign_note(
                content=payload,
                tenant_id=str(tenant.id),
                nota_id=str(signed_note.id),
                medico_nombre=tenant.nombre_medico,
                medico_cedula=tenant.cedula,
                medico_especialidad=tenant.especialidad or "General",
            )
            signed_note.firma_digital = signature["firma_digital"]
            signed_note.firma_hash_contenido = signature["firma_hash_contenido"]
            signed_note.firma_kms_key_id = signature["firma_kms_key_id"]
            signed_note.firma_algoritmo = signature["firma_algoritmo"]
            signed_note.firmado_en = signature["firmado_en"]
            signed_note.firmado_por = tenant.id
            signed_note.medico_nombre = tenant.nombre_medico
            signed_note.medico_cedula = tenant.cedula
            signed_note.medico_especialidad = tenant.especialidad
            signed_note.es_editable = False
            signed_note.estado = "signed"

            draft_note = Nota(
                tenant_id=tenant.id,
                expediente_id=expediente.id,
                tipo_nota="evolucion",
                contenido=json.dumps({"diagnosticos": ["Seguimiento post procedimiento"]}, ensure_ascii=False),
                signos_vitales={"frecuencia_cardiaca": 76, "frecuencia_respiratoria": 17, "temperatura": 36.6, "tension_arterial": "120/78"},
                motivo_consulta="Seguimiento de evolucion.",
                exploracion_fisica="Pendiente de completar.",
                plan_tratamiento="Pendiente de completar.",
                creado_por=tenant.id,
                estado="draft",
                es_editable=True,
            )
            session.add(draft_note)

            session.add(
                Receta(
                    tenant_id=tenant.id,
                    nota_id=signed_note.id,
                    medicamentos=[{"descripcion": "Paracetamol 500 mg VO cada 8 horas por 48 horas si dolor."}],
                    indicaciones_generales="Evitar masaje o ejercicio intenso por 24 horas.",
                )
            )
            session.add(
                Cita(
                    tenant_id=tenant.id,
                    paciente_id=paciente.id,
                    titulo="Seguimiento post procedimiento",
                    fecha_inicio=datetime.now(UTC) + timedelta(days=14),
                    fecha_fin=datetime.now(UTC) + timedelta(days=14, minutes=30),
                    estado="Programada",
                    notas="Revisar resultado y fotos de seguimiento.",
                )
            )
            session.add(
                AuditLog(
                    tenant_id=tenant.id,
                    tabla="demo",
                    registro_id=uuid.uuid4(),
                    accion="SEED",
                    method="POST",
                    path="/scripts/seed_beta_demo",
                    status_code=201,
                )
            )
            print("Demo beta listo: demo@cloudmedrecord.mx")


if __name__ == "__main__":
    asyncio.run(main())
