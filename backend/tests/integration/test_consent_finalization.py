import base64
import uuid
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

import app.api.v1.consentimientos as consent_api
from app.db.session import _get_session_factory
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
from scripts.verify_registry import verify_consentimientos
from tests.conftest import TENANT_A_ID, TENANT_B_ID, use_migrations

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.migration_schema,
    pytest.mark.skipif(not use_migrations(), reason="Fase 5 requires migrated triggers/RLS"),
]

_PNG_URL = "data:image/png;base64," + base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z3ZkAAAAASUVORK5CYII="
    )
).decode()


async def _seed_two_witness_template() -> str:
    template_key = f"fase5_testigos_{uuid.uuid4().hex[:8]}"
    factory = _get_session_factory()
    async with factory() as session, session.begin():
        template = ConsentimientoPlantilla(
            template_key=template_key,
            categoria="prueba",
            especialidad="General",
            procedimiento="Procedimiento con testigos",
            estado="activa",
        )
        session.add(template)
        await session.flush([template])
        session.add(
            ConsentimientoPlantillaVersion(
                plantilla_id=template.id,
                version="1.0",
                nombre="Consentimiento con dos testigos",
                contenido={
                    "descripcion": "Descripción",
                    "beneficios": "Beneficios",
                    "alternativas": "Alternativas",
                    "cuidados": "Cuidados",
                    "riesgos": "Riesgos",
                    "declaracion": "Declaración",
                    "aviso_producto": "Aviso",
                },
                campos=[
                    {
                        "key": "procedimiento",
                        "label": "Procedimiento",
                        "type": "text",
                        "required": True,
                        "max_length": 200,
                    }
                ],
                firmas_requeridas={"paciente": True, "medico": True, "testigos": 2},
                referencias_normativas=[],
                estado="publicada",
                contenido_hash="f" * 64,
                publicada_en=datetime.now(timezone.utc),
            )
        )
    return template_key


async def _seed_patient_and_record() -> tuple[uuid.UUID, uuid.UUID]:
    patient_id = uuid.uuid4()
    expediente_id = uuid.uuid4()
    factory = _get_session_factory()
    async with factory() as session, session.begin():
        session.add(
            Paciente(
                id=patient_id,
                tenant_id=uuid.UUID(TENANT_A_ID),
                nombre_completo="Paciente Fase Cinco",
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
                folio=f"F5-{uuid.uuid4().hex[:12]}",
                creado_por=uuid.UUID(TENANT_A_ID),
            )
        )
    return patient_id, expediente_id


async def test_fase5_finalizes_once_reprints_same_object_and_revokes_laterally(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    template_key = await _seed_two_witness_template()
    patient_id, expediente_id = await _seed_patient_and_record()
    headers = {"X-Tenant-ID": TENANT_A_ID}
    credentials = await client.get("/api/v1/consentimientos/credenciales-firma", headers=headers)
    assert credentials.status_code == 200, credentials.text
    credential_id = credentials.json()[0]["credencial_id"]

    created = await client.post(
        "/api/v1/consentimientos",
        json={
            "paciente_id": str(patient_id),
            "expediente_id": str(expediente_id),
            "template_key": template_key,
            "procedimiento": "Procedimiento controlado",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    consent_id = created.json()["id"]

    signed_human = await client.post(
        f"/api/v1/consentimientos/{consent_id}/firmar-paciente",
        json={
            "nombre_completo": "Representante Fase Cinco",
            "firma_paciente_base64": _PNG_URL,
            "aceptado": True,
            "tipo_firmante": "representante",
            "relacion_paciente": "Madre",
            "motivo_representacion": "Paciente menor de edad para esta prueba",
            "testigos": [
                {"nombre_completo": "Testigo Uno", "firma_base64": _PNG_URL},
                {"nombre_completo": "Testigo Dos", "firma_base64": _PNG_URL},
            ],
        },
        headers=headers,
    )
    assert signed_human.status_code == 200, signed_human.text
    assert len(signed_human.json()["firmantes"]) == 3

    calls = {"sign": 0, "store": 0}
    original_sign = consent_api.sign_note
    original_store = consent_api.store_final_consent_pdf

    def counted_sign(*args, **kwargs):
        calls["sign"] += 1
        return original_sign(*args, **kwargs)

    def counted_store(*args, **kwargs):
        calls["store"] += 1
        return original_store(*args, **kwargs)

    monkeypatch.setattr(consent_api, "sign_note", counted_sign)
    monkeypatch.setattr(consent_api, "store_final_consent_pdf", counted_store)

    final = await client.post(
        f"/api/v1/consentimientos/{consent_id}/firmar-medico",
        json={"credencial_id": credential_id},
        headers=headers,
    )
    assert final.status_code == 200, final.text
    final_payload = final.json()
    assert final_payload["status"] == "signed"
    assert final_payload["documento_final"]["s3_key"].endswith("/final.pdf")
    assert calls == {"sign": 1, "store": 1}

    repeated = await client.post(
        f"/api/v1/consentimientos/{consent_id}/firmar-medico",
        json={"credencial_id": credential_id},
        headers=headers,
    )
    assert repeated.status_code in (400, 409)
    assert calls == {"sign": 1, "store": 1}

    first_print = await client.get(
        f"/api/v1/consentimientos/{consent_id}/print", headers=headers
    )
    second_print = await client.get(
        f"/api/v1/consentimientos/{consent_id}/print", headers=headers
    )
    assert first_print.status_code == second_print.status_code == 200
    assert first_print.json()["documento_final"]["s3_key"] == second_print.json()[
        "documento_final"
    ]["s3_key"]
    assert first_print.json()["documento_final"]["s3_version_id"] == second_print.json()[
        "documento_final"
    ]["s3_version_id"]
    assert calls == {"sign": 1, "store": 1}

    token = urlparse(final_payload["verification_url"]).path.rsplit("/", 1)[-1]
    verified = await client.get(f"/verify/{token}")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["final_document"] is True

    factory = _get_session_factory()
    async with factory() as session, session.begin():
        before = (
            await session.execute(
                text("SELECT to_jsonb(c) FROM consentimientos c WHERE id=:id"),
                {"id": consent_id},
            )
        ).scalar_one()

    revoked = await client.post(
        f"/api/v1/consentimientos/{consent_id}/revocar",
        json={"motivo": "El paciente retiró expresamente su autorización"},
        headers=headers,
    )
    assert revoked.status_code == 201, revoked.text
    assert revoked.json()["revocacion"] is not None

    async with factory() as session, session.begin():
        after = (
            await session.execute(
                text("SELECT to_jsonb(c) FROM consentimientos c WHERE id=:id"),
                {"id": consent_id},
            )
        ).scalar_one()
        assert before == after, "revocation must never mutate the signed original"
        assert (
            await session.execute(
                select(ConsentimientoDocumentoFinal).where(
                    ConsentimientoDocumentoFinal.consentimiento_id == uuid.UUID(consent_id)
                )
            )
        ).scalar_one()

    verified_revoked = await client.get(f"/verify/{token}")
    assert verified_revoked.json()["status"] == "revoked"
    assert verified_revoked.json()["valid"] is False


async def test_fase5_rls_immutability_and_prod_verifier() -> None:
    verification = await verify_consentimientos()
    assert verification["ok"] is True, verification

    factory = _get_session_factory()
    async with factory() as session, session.begin():
        signed = (
            await session.execute(
                select(Consentimiento).where(Consentimiento.firma_kms_key_id.is_not(None)).limit(1)
            )
        ).scalar_one_or_none()
        if signed is not None:
            with pytest.raises(DBAPIError, match="immutable"):
                await session.execute(
                    text("UPDATE consentimientos SET procedimiento='alterado' WHERE id=:id"),
                    {"id": signed.id},
                )

    # A tenant cannot see another tenant's lateral signature evidence.
    async with factory() as session, session.begin():
        await session.execute(text("SET LOCAL ROLE medrecord_app"))
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"), {"t": TENANT_B_ID}
        )
        count = (
            await session.execute(select(ConsentimientoFirmante))
        ).scalars().all()
        assert all(row.tenant_id == uuid.UUID(TENANT_B_ID) for row in count)

    # Models stay reachable so create_all and Alembic metadata remain in sync.
    assert ConsentimientoRevocacion.__tablename__ == "consentimiento_revocaciones"
