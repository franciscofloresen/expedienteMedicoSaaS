"""Fase 13 — clinical-photo metadata: CRUD, validation, tenant isolation.

The image bytes go through the clinical-file S3 pipeline (not exercised here); we
insert a clinical_files row directly and test the metadata sidecar over it.
"""

import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest import TENANT_A_ID, TENANT_B_ID, use_migrations

pytestmark = pytest.mark.asyncio

_A = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
_B = {"X-Tenant-ID": TENANT_B_ID, "X-Plan": "pro"}

# Patients created here use CURP prefix FFFF9001. In create_all mode the test DB is
# session-scoped, so these tests must delete their own paciente/expediente rows —
# otherwise the expedientes accumulate under tenant A and trip the basico
# max_expedientes=5 limit in a later, plan-limited test (test_notas). Migration mode
# is throwaway and delete-protected, so cleanup is skipped there.
@pytest_asyncio.fixture(autouse=True)
async def _cleanup_created_rows(setup_database):
    yield
    if use_migrations():
        return
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM fotografias_clinicas WHERE paciente_id IN "
                 "(SELECT id FROM pacientes WHERE curp LIKE 'FFFF9001%')")
        )
        await conn.execute(
            text("DELETE FROM clinical_files WHERE paciente_id IN "
                 "(SELECT id FROM pacientes WHERE curp LIKE 'FFFF9001%')")
        )
        await conn.execute(
            text("DELETE FROM expedientes WHERE paciente_id IN "
                 "(SELECT id FROM pacientes WHERE curp LIKE 'FFFF9001%')")
        )
        await conn.execute(text("DELETE FROM pacientes WHERE curp LIKE 'FFFF9001%'"))
    await engine.dispose()


async def _patient_and_expediente(client: AsyncClient, curp: str) -> tuple[str, str]:
    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Foto",
            "sexo": "F",
            "fecha_nacimiento": "1990-01-01",
            "curp": curp,
            "telefono": "555-000-3434",
            "domicilio": "Calle Foto 1",
            "ocupacion": "Modelo",
        },
        headers=_A,
    )
    assert res.status_code == 201, res.text
    pid = res.json()["id"]
    res = await client.post("/api/v1/expedientes/", json={"paciente_id": pid}, headers=_A)
    assert res.status_code == 201, res.text
    return pid, res.json()["id"]


async def _insert_clinical_file(paciente_id: str, expediente_id: str) -> str:
    """Insert a clinical_files row directly (bypassing the S3 upload flow)."""
    file_id = str(uuid.uuid4())
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO clinical_files
                    (id, tenant_id, paciente_id, expediente_id, s3_key, original_filename,
                     content_type, size_bytes, category, status, scan_status, uploaded_by)
                VALUES
                    (:id, :tenant, :pac, :exp, :key, 'foto.jpg', 'image/jpeg', 12345,
                     'fotografia_clinica', 'completed', 'clean', 'test')
                """
            ),
            {
                "id": file_id,
                "tenant": TENANT_A_ID,
                "pac": paciente_id,
                "exp": expediente_id,
                "key": f"tenant/{TENANT_A_ID}/{file_id}.jpg",
            },
        )
    await engine.dispose()
    return file_id


async def test_fotografia_crud_and_metadata(client: AsyncClient, setup_database) -> None:
    pid, eid = await _patient_and_expediente(client, "FFFF900101MDFXYZ01")
    file_id = await _insert_clinical_file(pid, eid)

    res = await client.post(
        "/api/v1/fotografias/",
        json={
            "paciente_id": pid,
            "clinical_file_id": file_id,
            "categoria": "antes",
            "lateralidad": "derecha",
            "zona_anatomica": "Mejilla",
            "grupo_comparacion": "rejuvenecimiento-2026",
        },
        headers=_A,
    )
    assert res.status_code == 201, res.text
    foto = res.json()
    fid = foto["id"]
    assert foto["categoria"] == "antes"
    assert foto["grupo_comparacion"] == "rejuvenecimiento-2026"

    upd = await client.put(
        f"/api/v1/fotografias/{fid}",
        json={"categoria": "despues", "zona_anatomica": "Mejilla", "grupo_comparacion": "rejuvenecimiento-2026"},
        headers=_A,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["categoria"] == "despues"

    listed = await client.get(f"/api/v1/fotografias/?paciente_id={pid}", headers=_A)
    assert any(f["id"] == fid for f in listed.json())

    assert (await client.delete(f"/api/v1/fotografias/{fid}", headers=_A)).status_code == 204


async def test_fotografia_rejects_bad_categoria(client: AsyncClient, setup_database) -> None:
    pid, eid = await _patient_and_expediente(client, "FFFF900101MDFXYZ02")
    file_id = await _insert_clinical_file(pid, eid)
    res = await client.post(
        "/api/v1/fotografias/",
        json={"paciente_id": pid, "clinical_file_id": file_id, "categoria": "biometria"},
        headers=_A,
    )
    assert res.status_code == 422


async def test_fotografias_are_tenant_isolated(client: AsyncClient, setup_database) -> None:
    pid, eid = await _patient_and_expediente(client, "FFFF900101MDFXYZ03")
    file_id = await _insert_clinical_file(pid, eid)
    res = await client.post(
        "/api/v1/fotografias/",
        json={"paciente_id": pid, "clinical_file_id": file_id, "categoria": "general"},
        headers=_A,
    )
    assert res.status_code == 201, res.text
    fid = res.json()["id"]

    b_list = await client.get(f"/api/v1/fotografias/?paciente_id={pid}", headers=_B)
    assert all(f["id"] != fid for f in b_list.json())
    assert (await client.delete(f"/api/v1/fotografias/{fid}", headers=_B)).status_code == 404
