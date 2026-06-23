from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_expedientes_flow(
    client: AsyncClient, db_session: AsyncSession, seed_tenant_a
):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    # 1. Create Patient
    patient_data = {
        "nombre_completo": "Paciente Expediente Test",
        "sexo": "X",
        "fecha_nacimiento": "2000-01-01",
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201
    patient_id = res.json()["id"]

    # 2. Create Expediente
    exp_data = {"paciente_id": patient_id, "antecedentes": "Alergia a la penicilina."}
    res = await client.post("/api/v1/expedientes/", json=exp_data, headers=headers)
    assert res.status_code == 201
    expediente_id = res.json()["id"]

    # 3. Read Expediente (Check decryption)
    res = await client.get(
        f"/api/v1/expedientes/paciente/{patient_id}", headers=headers
    )
    assert res.status_code == 200
    exp = res.json()
    assert exp["antecedentes"] == "Alergia a la penicilina."

    # 4. Update Expediente
    update_data = {"antecedentes": "Alergia a la penicilina. Hipertensión."}
    res = await client.put(
        f"/api/v1/expedientes/{expediente_id}/antecedentes",
        json=update_data,
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 5. List Expedientes
    res = await client.get("/api/v1/expedientes/", headers=headers)
    assert res.status_code == 200
    exps = res.json()
    assert len(exps) >= 1

    # 6. Export PDF (Removido porque pdf.py fue eliminado)
    pass


@pytest.mark.asyncio
async def test_expediente_invalid_patient(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    exp_data = {"paciente_id": str(uuid4())}
    res = await client.post("/api/v1/expedientes/", json=exp_data, headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_invalid(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    res = await client.get(f"/api/v1/expedientes/{uuid4()}/export", headers=headers)
    assert res.status_code == 404
