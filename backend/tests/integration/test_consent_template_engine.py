import uuid
from datetime import date
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import _get_session_factory
from app.models.consentimiento_plantilla import ConsentimientoPlantillaVersion
from app.models.expediente import Expediente
from app.models.paciente import Paciente
from scripts.import_consent_templates import run_import
from scripts.verify_registry import verify_plantillas
from tests.conftest import use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(
        not use_migrations(),
        reason="published-template privileges/triggers require the migrated schema",
    ),
]


async def test_import_is_idempotent_and_verify_plantillas_passes() -> None:
    first = await run_import("apply")
    second = await run_import("apply")

    assert first["ok"] is True
    assert first["counts"]["versions_inserted"] in (0, 5)
    assert second["ok"] is True
    assert second["counts"]["versions_inserted"] == 0
    assert second["counts"]["versions_unchanged"] == 5

    verification = await verify_plantillas()
    assert verification["ok"] is True, verification
    assert verification["counts"]["publicadas"] == 5


async def test_published_version_content_is_immutable(db_session: AsyncSession) -> None:
    await run_import("apply")
    version_id = (
        await db_session.execute(
            select(ConsentimientoPlantillaVersion.id).where(
                ConsentimientoPlantillaVersion.estado == "publicada"
            )
        )
    ).scalars().first()
    assert version_id is not None

    with pytest.raises(DBAPIError, match="immutable"):
        await db_session.execute(
            text(
                "UPDATE consentimiento_plantilla_versiones "
                "SET nombre = 'Contenido alterado' WHERE id = :id"
            ),
            {"id": version_id},
        )
        await db_session.flush()


async def test_consentimiento_uses_version_snapshot_and_signing_regression(
    client: AsyncClient,
    seed_tenant_a: None,
) -> None:
    from tests.conftest import TENANT_A_ID

    await run_import("apply")
    headers = {"X-Tenant-ID": TENANT_A_ID}
    patient_id = uuid.uuid4()
    expediente_id = uuid.uuid4()
    factory = _get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            Paciente(
                id=patient_id,
                tenant_id=uuid.UUID(TENANT_A_ID),
                nombre_completo="Paciente Consentimiento Fase 4",
                sexo="X",
                fecha_nacimiento=date(1990, 1, 1),
            )
        )
        await session.flush()
        session.add(
            Expediente(
                id=expediente_id,
                tenant_id=uuid.UUID(TENANT_A_ID),
                paciente_id=patient_id,
                folio=f"F4-{uuid.uuid4().hex[:12]}",
                creado_por=uuid.UUID(TENANT_A_ID),
            )
        )

    templates = await client.get(
        "/api/v1/consentimientos/templates?especialidad=Dermatología",
        headers=headers,
    )
    assert templates.status_code == 200
    assert len(templates.json()) == 4

    created = await client.post(
        "/api/v1/consentimientos",
        json={
            "paciente_id": str(patient_id),
            "expediente_id": str(expediente_id),
            "template_key": "general_atencion",
            "procedimiento": "Valoración clínica",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    consent = created.json()
    assert consent["version"] == "1.0"
    assert consent["plantilla_version_id"] is not None
    assert consent["contenido_renderizado"].startswith(
        "Consentimiento general de atención médica\n\nPaciente: Paciente Consentimiento Fase 4"
    )

    patient_signed = await client.post(
        f"/api/v1/consentimientos/{consent['id']}/firmar-paciente",
        json={
            "nombre_completo": "Paciente Consentimiento Fase 4",
            "firma_paciente_base64": "data:image/png;base64,ZmlybWE=",
            "aceptado": True,
        },
        headers=headers,
    )
    assert patient_signed.status_code == 200, patient_signed.text

    doctor_signed = await client.post(
        f"/api/v1/consentimientos/{consent['id']}/firmar-medico",
        headers=headers,
    )
    assert doctor_signed.status_code == 200, doctor_signed.text
    signed = doctor_signed.json()
    assert signed["status"] == "signed"
    assert signed["hash_contenido"]

    token = urlparse(signed["verification_url"]).path.rsplit("/", 1)[-1]
    verified = await client.get(f"/verify/{token}")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["resource_type"] == "consentimiento"
