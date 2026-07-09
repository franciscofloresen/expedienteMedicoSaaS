"""
Regression test for the NOM-004 immutability trigger blocking note signing.

The prod bug: `firmar_nota` used to UPDATE the notas row twice — once to persist
the signature (flipping es_editable=false) and again to attach
verification_token_id. The `notas_signed_immutable` trigger (installed via
migration, NOT via create_all) raises on the second UPDATE because the note is
already signed, surfacing as an unguarded 500. The same trap existed on the
GET /print & /legal-preview paths, which wrote verification_token_id back onto an
already-signed note.

The regular suite never caught this because conftest builds the schema with
create_all, which does not include the raw-SQL trigger. These tests install the
real trigger so signing/printing run exactly as they do in production.

The tests clean up every row they commit (paciente/expediente/nota/token) so they
do not consume tenant A's shared `basico` plan quota (max_expedientes=5), and they
create expedientes with X-Plan: pro so their own creates never hit that cap.
"""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TENANT_A_ID

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def signed_note_immutability_trigger(setup_database):
    """Install the production NOM-004 immutability trigger on the test DB.

    Mirrors backend/alembic/versions/a1b2c3d4e5f6_rls_audit_immutability.py so the
    signing flow runs against the same DB rule as production. Dropped on teardown
    to keep other tests isolated.
    """
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
        await conn.execute(
            text("DROP TRIGGER IF EXISTS notas_signed_immutable ON notas")
        )
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
        await conn.execute(
            text("DROP TRIGGER IF EXISTS notas_signed_immutable ON notas")
        )
        await conn.execute(
            text("DROP FUNCTION IF EXISTS prevent_signed_note_modification()")
        )
    await engine.dispose()


async def _purge_chain(
    paciente_id: str | None = None,
    expediente_id: str | None = None,
    nota_id: str | None = None,
) -> None:
    """Delete committed rows in FK-safe order (superuser bypasses RLS; no DELETE
    triggers are installed in the test DB)."""
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        if nota_id:
            # Delete the note first: it holds the FK to verification_tokens.
            await conn.execute(
                text("DELETE FROM notas WHERE id = :id"), {"id": nota_id}
            )
            await conn.execute(
                text("DELETE FROM verification_tokens WHERE resource_id = :rid"),
                {"rid": nota_id},
            )
        if expediente_id:
            await conn.execute(
                text("DELETE FROM expedientes WHERE id = :id"), {"id": expediente_id}
            )
        if paciente_id:
            await conn.execute(
                text("DELETE FROM pacientes WHERE id = :id"), {"id": paciente_id}
            )
    await engine.dispose()


async def _create_draft_note(
    client: AsyncClient, headers: dict, curp: str
) -> tuple[str, str, str]:
    patient_data = {
        "nombre_completo": "Paciente Firma Trigger",
        "sexo": "F",
        "fecha_nacimiento": "1990-01-01",
        "curp": curp,
        "telefono": "555-000-2222",
        "domicilio": "Calle Falsa 456",
        "ocupacion": "Ingeniera",
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201, res.text
    patient_id = res.json()["id"]

    res = await client.post(
        "/api/v1/expedientes/", json={"paciente_id": patient_id}, headers=headers
    )
    assert res.status_code == 201, res.text
    expediente_id = res.json()["id"]

    draft = {
        "expediente_id": expediente_id,
        "tipo_nota": "evolucion",
        "contenido": {"evolucion_y_actualizacion_cuadro": "Estable."},
        "signos_vitales": {
            "frecuencia_cardiaca": 80,
            "frecuencia_respiratoria": 16,
            "temperatura": 36.5,
            "tension_arterial": "120/80",
        },
        "diagnosticos": ["Migraña"],
        "tratamiento": "Paracetamol",
    }
    res = await client.post("/api/v1/notas/", json=draft, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"], expediente_id, patient_id


async def test_sign_note_succeeds_with_immutability_trigger(
    client: AsyncClient, signed_note_immutability_trigger
):
    """Signing must return 200 even with the NOM-004 trigger active.

    Before the fix this 500'd: the trigger rejected the second UPDATE that
    attached verification_token_id after the note was already signed.
    """
    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
    nota_id, expediente_id, patient_id = await _create_draft_note(
        client, headers, "AAAA900101HDFXYZ09"
    )
    try:
        res = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=headers)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["firmada"] is True
        assert body["es_editable"] is False
        assert body["medico_cedula"]
        # Token link must have been attached in the same UPDATE that signed the note.
        assert body["verification_url"], "verification_url should be present"

        # The note is now genuinely immutable: a further edit is rejected (403),
        # confirming the trigger really is active during this test.
        res = await client.put(
            f"/api/v1/notas/{nota_id}",
            json={"contenido": {"evolucion_y_actualizacion_cuadro": "otra"}},
            headers=headers,
        )
        assert res.status_code == 403, res.text
    finally:
        await _purge_chain(patient_id, expediente_id, nota_id)


async def test_print_legacy_signed_note_without_token(
    client: AsyncClient, signed_note_immutability_trigger
):
    """GET /print must not 500 on a signed note whose verification_token_id is NULL.

    Reproduces legacy signed notes (signed before the token feature, or where token
    creation failed at signing). Before the fix, the print/legal-preview path wrote
    nota.verification_token_id, and that UPDATE on an already-signed note was rejected
    by the trigger at commit — an unguarded 500. An INSERT does not fire the BEFORE
    UPDATE trigger, so we materialise the legacy state directly.
    """
    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}

    patient_data = {
        "nombre_completo": "Paciente Legacy",
        "sexo": "M",
        "fecha_nacimiento": "1985-05-05",
        "curp": "BBBB850505HDFXYZ08",
        "telefono": "555-000-3333",
        "domicilio": "Calle Vieja 789",
        "ocupacion": "Docente",
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201, res.text
    patient_id = res.json()["id"]
    res = await client.post(
        "/api/v1/expedientes/", json={"paciente_id": patient_id}, headers=headers
    )
    assert res.status_code == 201, res.text
    expediente_id = res.json()["id"]

    # Insert an already-signed, token-less note directly (superuser bypasses RLS;
    # INSERT does not fire the UPDATE immutability trigger).
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        row = await conn.execute(
            text(
                """
                INSERT INTO notas (
                    expediente_id, tenant_id, tipo_nota, contenido, estado,
                    firma_digital, firma_hash_contenido, firma_kms_key_id,
                    firma_algoritmo, firmado_por, firmado_en, es_editable,
                    medico_nombre, medico_cedula, medico_especialidad,
                    verification_token_id
                )
                VALUES (
                    :exp, :tenant, 'evolucion', '{}', 'signed',
                    '\\x0102'::bytea, :hash, 'local-dev-key',
                    'ECDSA_SHA_256', :tenant, now(), false,
                    'Dr. Legacy', 'CED-A-001', 'General',
                    NULL
                )
                RETURNING id
                """
            ),
            {"exp": expediente_id, "tenant": TENANT_A_ID, "hash": "a" * 64},
        )
        nota_id = str(row.scalar_one())
    await engine.dispose()

    try:
        # Before the fix this 500'd (write-back to a signed note hits the trigger).
        res = await client.get(f"/api/v1/notas/{nota_id}/print", headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["firma"]["verification_url"], "verification_url expected"

        # legal-preview shares the same code path.
        res = await client.get(
            f"/api/v1/notas/{nota_id}/legal-preview", headers=headers
        )
        assert res.status_code == 200, res.text
    finally:
        await _purge_chain(patient_id, expediente_id, nota_id)
