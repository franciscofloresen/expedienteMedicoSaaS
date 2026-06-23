from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_pacientes_crud(
    client: AsyncClient, db_session: AsyncSession, seed_tenant_a
):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    # 1. Create Patient
    patient_data = {
        "nombre_completo": "Paciente CRUD Test",
        "sexo": "M",
        "fecha_nacimiento": "1990-01-01",
        "curp": "AAAA900101HDFXYZ11",
        "telefono": "555-123-4567",
        "domicilio": "123 Main St",
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201
    patient_id = res.json()["id"]

    # 2. Read Patient (Verify decryption)
    res = await client.get(f"/api/v1/pacientes/{patient_id}", headers=headers)
    assert res.status_code == 200
    pat = res.json()
    assert pat["domicilio"] == "123 Main St"

    # 3. List Patients
    res = await client.get("/api/v1/pacientes/", headers=headers)
    assert res.status_code == 200
    pats = res.json()
    assert len(pats) >= 1

    # 4. Search Patients
    res = await client.get("/api/v1/pacientes/?q=CRUD", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 5. Update Patient
    update_data = {"telefono": "999-888-7777"}
    res = await client.put(
        f"/api/v1/pacientes/{patient_id}", json=update_data, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_paciente_not_found(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    res = await client.get(f"/api/v1/pacientes/{uuid4()}", headers=headers)
    assert res.status_code == 404
