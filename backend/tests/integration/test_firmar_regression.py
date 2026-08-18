"""Standing `firmar` regression: create → firmar → verificar, end to end.

PLAN_EJECUCION_V2 §1 makes this mandatory after any phase that touches `notas` or
`consentimientos` — it is the descendant of the firmar-500/CORS incident (the NOM-004
immutability trigger rejecting the post-signing verification_token_id UPDATE). It lives
in the CI migration job via `@pytest.mark.migration_schema`, so it runs against the REAL
Alembic trigger/RLS/grants, exactly as production signs.

Fase 1 tie-in: the doctor identity stamped on the signature now flows through the
`get_credencial_para_firma` adapter (medicos/medico_credenciales), so this asserts the
signed note carries the tenant's default-credential number and that the signature still
verifies mathematically.
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TENANT_A_ID, use_migrations

pytestmark = [pytest.mark.asyncio, pytest.mark.migration_schema]

# Tenant A's cédula (conftest seeds it; the Fase 1 backfill makes it the default
# credential number). Adapter and fallback both yield this, so it holds in both modes.
_TENANT_A_CEDULA = "CED-A-001"


@pytest_asyncio.fixture
async def signed_note_trigger(setup_database):
    """Ensure the NOM-004 signed-note immutability trigger is present.

    In migration mode the real Alembic trigger already exists (no-op here). In
    create_all mode we install the production mirror so the firmar write-back path is
    exercised against the same rule, then drop it on teardown.
    """
    if use_migrations():
        yield
        return

    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION prevent_signed_note_modification()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF OLD.es_editable = false THEN
                        RAISE EXCEPTION 'Signed medical notes cannot be modified '
                        '(NOM-004 compliance). Use an amendment note instead.';
                        RETURN NULL;
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            )
        )
        await conn.execute(text("DROP TRIGGER IF EXISTS notas_signed_immutable ON notas"))
        await conn.execute(
            text(
                """
                CREATE TRIGGER notas_signed_immutable
                BEFORE UPDATE ON notas
                FOR EACH ROW
                EXECUTE FUNCTION prevent_signed_note_modification()
                """
            )
        )
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DROP TRIGGER IF EXISTS notas_signed_immutable ON notas"))
        await conn.execute(text("DROP FUNCTION IF EXISTS prevent_signed_note_modification()"))
    await engine.dispose()


async def _purge_chain(paciente_id: str, expediente_id: str, nota_id: str) -> None:
    """Delete committed rows (create_all mode only). In migration mode the real
    prevent_*_deletion triggers block DELETE and the DB is throwaway, so skip it."""
    if use_migrations():
        return
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM notas WHERE id = :id"), {"id": nota_id})
        await conn.execute(
            text("DELETE FROM verification_tokens WHERE resource_id = :rid"), {"rid": nota_id}
        )
        await conn.execute(text("DELETE FROM expedientes WHERE id = :id"), {"id": expediente_id})
        await conn.execute(text("DELETE FROM pacientes WHERE id = :id"), {"id": paciente_id})
    await engine.dispose()


async def _create_draft_note(client: AsyncClient, headers: dict, curp: str) -> tuple[str, str, str]:
    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Firma Regresión",
            "sexo": "F",
            "fecha_nacimiento": "1990-01-01",
            "curp": curp,
            "telefono": "555-000-4444",
            "domicilio": "Calle Real 123",
            "ocupacion": "Arquitecta",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    patient_id = res.json()["id"]

    res = await client.post(
        "/api/v1/expedientes/", json={"paciente_id": patient_id}, headers=headers
    )
    assert res.status_code == 201, res.text
    expediente_id = res.json()["id"]

    res = await client.post(
        "/api/v1/notas/",
        json={
            "expediente_id": expediente_id,
            "tipo_nota": "evolucion",
            "contenido": {"evolucion_y_actualizacion_cuadro": "Estable."},
            "signos_vitales": {
                "frecuencia_cardiaca": 78,
                "frecuencia_respiratoria": 16,
                "temperatura": 36.6,
                "tension_arterial": "118/76",
            },
            "diagnosticos": ["Cefalea"],
            "tratamiento": "Reposo",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"], expediente_id, patient_id


async def test_crear_firmar_verificar_end_to_end(
    client: AsyncClient, signed_note_trigger
) -> None:
    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
    nota_id, expediente_id, patient_id = await _create_draft_note(
        client, headers, "CCCC900101MDFXYZ07"
    )
    try:
        # firmar → 200, and the signer identity comes from the Fase 1 credential.
        res = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=headers)
        assert res.status_code == 200, res.text
        signed = res.json()
        assert signed["firmada"] is True
        assert signed["es_editable"] is False
        assert signed["medico_cedula"] == _TENANT_A_CEDULA
        assert signed["verification_url"], "verification_url should be attached at signing"

        # verificar → the signature validates mathematically and carries the same identity.
        res = await client.get(f"/api/v1/notas/{nota_id}/verificar-firma", headers=headers)
        assert res.status_code == 200, res.text
        verified = res.json()
        assert verified["firmada"] is True
        assert verified["valid"] is True, f"signature must verify: {verified}"
        assert verified["medico_cedula"] == _TENANT_A_CEDULA
    finally:
        await _purge_chain(patient_id, expediente_id, nota_id)


async def test_double_click_firma_does_not_double_sign(
    client: AsyncClient, signed_note_trigger
) -> None:
    """Fase 11 idempotency: a second firmar (double click) is rejected with 400 and
    the note keeps its original, single signature — never a second sign or a 500."""
    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
    nota_id, expediente_id, patient_id = await _create_draft_note(
        client, headers, "CCCC900101MDFXYZ08"
    )
    try:
        first = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=headers)
        assert first.status_code == 200, first.text
        original_hash = first.json()["firma_hash_contenido"]

        # Second click on an already-signed note: rejected, not re-signed.
        second = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=headers)
        assert second.status_code == 400, second.text
        assert "firmada" in second.text.lower()

        # The stored signature is unchanged and still verifies.
        verified = (
            await client.get(f"/api/v1/notas/{nota_id}/verificar-firma", headers=headers)
        ).json()
        assert verified["valid"] is True
        assert verified["firma_hash_contenido"] == original_hash
    finally:
        await _purge_chain(patient_id, expediente_id, nota_id)


async def test_signing_stamps_credential_on_encuentro(
    client: AsyncClient, signed_note_trigger
) -> None:
    """Fase 12 §9 (Fase 2 debt): signing a note that belongs to an encuentro stamps
    the signing credential on the encuentro (mutable side), while the signed note is
    never UPDATEd again. Runs in migration mode, where a real credential is seeded."""
    if not use_migrations():
        # create_all mode has no seeded médico/credential, so the signing adapter
        # falls back to a credential with no id — nothing to stamp. The behavior is
        # verified in migration mode (the CI trigger/RLS job), matching production.
        pytest.skip("encuentro credential stamping needs the seeded credential (migration mode)")

    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}

    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Encuentro Credencial",
            "sexo": "F",
            "fecha_nacimiento": "1988-05-05",
            "curp": "CCCC880505MDFXYZ09",
            "telefono": "555-000-7777",
            "domicilio": "Calle Cred 9",
            "ocupacion": "Ingeniera",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    patient_id = res.json()["id"]

    res = await client.post(
        "/api/v1/expedientes/", json={"paciente_id": patient_id}, headers=headers
    )
    assert res.status_code == 201, res.text
    expediente_id = res.json()["id"]

    res = await client.post(
        "/api/v1/encuentros/",
        json={"expediente_id": expediente_id, "tipo": "subsecuente"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    encuentro_id = res.json()["id"]

    res = await client.post(
        "/api/v1/notas/",
        json={
            "expediente_id": expediente_id,
            "tipo_nota": "evolucion",
            "contenido": {"evolucion_y_actualizacion_cuadro": "Estable."},
            "encuentro_clinico_id": encuentro_id,
            "signos_vitales": {
                "frecuencia_cardiaca": 78,
                "frecuencia_respiratoria": 16,
                "temperatura": 36.6,
                "tension_arterial": "118/76",
            },
            "diagnosticos": ["Cefalea"],
            "tratamiento": "Reposo",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    nota_id = res.json()["id"]

    try:
        # Before signing, the encuentro credential link is still NULL (§5.2).
        engine = create_async_engine(os.environ["DATABASE_URL"])
        async with engine.connect() as conn:
            before = (
                await conn.execute(
                    text("SELECT credencial_id FROM encuentros_clinicos WHERE id = :id"),
                    {"id": encuentro_id},
                )
            ).scalar_one()
        assert before is None

        res = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=headers)
        assert res.status_code == 200, res.text

        # After signing, the encuentro carries the signing credential.
        async with engine.connect() as conn:
            after = (
                await conn.execute(
                    text("SELECT credencial_id FROM encuentros_clinicos WHERE id = :id"),
                    {"id": encuentro_id},
                )
            ).scalar_one()
        assert after is not None, "encuentro.credencial_id must be stamped at signing"
        await engine.dispose()
    finally:
        await _purge_chain(patient_id, expediente_id, nota_id)
        if not use_migrations():
            cleanup = create_async_engine(os.environ["DATABASE_URL"])
            async with cleanup.begin() as conn:
                await conn.execute(
                    text("DELETE FROM encuentros_clinicos WHERE id = :id"), {"id": encuentro_id}
                )
            await cleanup.dispose()
