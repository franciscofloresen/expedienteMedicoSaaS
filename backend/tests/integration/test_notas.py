from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_notas_crud(client: AsyncClient, db_session: AsyncSession, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    # 1. Create Patient & Expediente
    patient_data = {
        "nombre_completo": "Paciente Notas Test",
        "sexo": "F",
        "fecha_nacimiento": "1995-01-01",
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201
    patient_id = res.json()["id"]

    exp_data = {"paciente_id": patient_id}
    res = await client.post("/api/v1/expedientes/", json=exp_data, headers=headers)
    assert res.status_code == 201
    expediente_id = res.json()["id"]

    # 2. Create Nota
    nota_data = {
        "expediente_id": expediente_id,
        "tipo_nota": "evolucion",
        "contenido": {"evolucion": "Mejora progresiva."},
        "diagnosticos": ["Migraña"],
        "signos_vitales": {"temperatura": 36.5},
    }
    res = await client.post("/api/v1/notas/", json=nota_data, headers=headers)
    assert res.status_code == 201
    nota_id = res.json()["id"]

    # 3. List Notas by Expediente
    res = await client.get(f"/api/v1/notas/expediente/{expediente_id}", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 4. Update Nota
    update_data = {"contenido": {"evolucion": "Completamente sano."}}
    res = await client.put(
        f"/api/v1/notas/{nota_id}", json=update_data, headers=headers
    )
    assert res.status_code == 200

    # 5. List Notas by Expediente
    res = await client.get(f"/api/v1/notas/expediente/{expediente_id}", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1


@pytest.mark.asyncio
async def test_nota_not_found(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    res = await client.get(f"/api/v1/notas/expediente/{uuid4()}", headers=headers)
    assert res.status_code == 200
    assert res.json() == []

@pytest.mark.asyncio
async def test_create_receta(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID
    headers = {"X-Tenant-ID": TENANT_A_ID}

    # 0. Create Paciente
    paciente_res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Notas Test",
            "sexo": "F",
            "fecha_nacimiento": "1995-01-01",
        },
        headers=headers,
    )
    assert paciente_res.status_code == 201
    paciente_id = paciente_res.json()["id"]

    # 1. Create Expediente
    exp_res = await client.post(
        "/api/v1/expedientes/",
        json={"paciente_id": paciente_id},
        headers=headers,
    )
    expediente_id = exp_res.json()["id"]

    # 2. Create Nota
    nota_res = await client.post(
        "/api/v1/notas/",
        json={
            "expediente_id": expediente_id,
            "tipo_nota": "evolucion",
            "contenido": {"test": "data"},
            "diagnosticos": ["Test Dx"],
            "signos_vitales": {"temperatura": 36.5}
        },
        headers=headers,
    )
    assert nota_res.status_code == 201
    nota_id = nota_res.json()["id"]

    # 3. Create Receta
    receta_data = {
        "nota_id": nota_id,
        "medicamentos": [{"descripcion": "Ibuprofeno"}],
        "indicaciones_generales": "Tomar 1 cada 8 hrs"
    }
    receta_res = await client.post("/api/v1/recetas", json=receta_data, headers=headers)
    assert receta_res.status_code == 200, receta_res.text
    assert receta_res.json()["nota_id"] == nota_id
