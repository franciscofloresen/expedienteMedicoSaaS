import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_citas_crud(client: AsyncClient, db_session: AsyncSession, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    # 1. Create Patient
    patient_data = {
        "nombre_completo": "Paciente para Citas",
        "sexo": "M",
        "fecha_nacimiento": "1980-05-15",
        "curp": "AAAA800515HDFXYZ02",
        "telefono": "555-000-2222",
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201
    patient_id = res.json()["id"]

    # 2. Create Cita
    cita_data = {
        "paciente_id": patient_id,
        "titulo": "Consulta de Seguimiento",
        "fecha_inicio": "2026-07-01T10:00:00Z",
        "fecha_fin": "2026-07-01T10:30:00Z",
        "estado": "Programada",
    }
    res = await client.post("/api/v1/citas/", json=cita_data, headers=headers)
    assert res.status_code == 201
    cita_id = res.json()["id"]

    # 3. List Citas
    res = await client.get("/api/v1/citas/", headers=headers)
    assert res.status_code == 200
    citas = res.json()
    assert len(citas) >= 1
    assert any(c["id"] == cita_id for c in citas)

    # 4. Filter Citas by Date
    res = await client.get(
        "/api/v1/citas/?start_date=2026-07-01T00:00:00Z&end_date=2026-07-01T23:59:59Z",
        headers=headers,
    )
    assert res.status_code == 200
    citas = res.json()
    assert len(citas) == 1
    assert citas[0]["titulo"] == "Consulta de Seguimiento"

    # 5. Update Cita
    update_data = {"estado": "Completada"}
    res = await client.put(
        f"/api/v1/citas/{cita_id}", json=update_data, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["estado"] == "Completada"

    # 6. Delete Cita
    res = await client.delete(f"/api/v1/citas/{cita_id}", headers=headers)
    assert res.status_code == 204

    # 7. Verify Delete
    res = await client.get("/api/v1/citas/", headers=headers)
    citas = res.json()
    assert not any(c["id"] == cita_id for c in citas)
