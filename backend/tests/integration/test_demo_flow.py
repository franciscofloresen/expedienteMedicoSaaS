import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.tenant import Tenant
from app.models.paciente import Paciente
from app.models.expediente import Expediente
from app.models.nota import Nota
from app.models.audit import AuditLog

@pytest.mark.asyncio
async def test_demo_flow(client: AsyncClient, db_session: AsyncSession):
    """
    E2E Test mirroring the local presentation flow:
    1. Register Doctor
    2. Login
    3. Create Patient
    4. Create Expediente
    5. Draft Note
    6. Update Draft
    7. Sign Note
    8. Verify Audit Log
    """
    
    # 1. Register Doctor
    register_data = {
        "nombre_medico": "Dr. Demo Test",
        "cedula": "DEMO-123",
        "especialidad": "General",
        "email": "dr.demo@test.com",
        "password": "Password123!"
    }
    
    res = await client.post("/api/v1/auth/register", json=register_data)
    assert res.status_code == 201
    auth_data = res.json()
    tenant_id = auth_data["tenant_id"]
    token = auth_data["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Login
    login_data = {
        "email": "dr.demo@test.com",
        "password": "Password123!"
    }
    res = await client.post("/api/v1/auth/login", json=login_data)
    assert res.status_code == 200
    
    # 3. Create Patient
    patient_data = {
        "nombre_completo": "Paciente de Prueba",
        "sexo": "F",
        "fecha_nacimiento": "1990-01-01",
        "curp": "AAAA900101HDFXYZ01",
        "telefono": "555-000-1111",
        "domicilio": "Calle Falsa 123",
        "ocupacion": "Ingeniera"
    }
    res = await client.post("/api/v1/pacientes/", json=patient_data, headers=headers)
    assert res.status_code == 201
    patient_id = res.json()["id"]
    
    # 4. Create Expediente
    exp_data = {
        "paciente_id": patient_id
    }
    res = await client.post("/api/v1/expedientes/", json=exp_data, headers=headers)
    assert res.status_code == 201
    expediente_id = res.json()["id"]
    
    # 5. Draft Note
    draft_data = {
        "expediente_id": expediente_id,
        "tipo_nota": "evolucion",
        "contenido": {"evolucion_y_actualizacion_cuadro": "Dolor leve."},
        "signos_vitales": {"frecuencia_cardiaca": 80, "frecuencia_respiratoria": 16, "temperatura": 36.5, "tension_arterial": "120/80"},
        "diagnosticos": ["Migraña"],
        "tratamiento": "Paracetamol"
    }
    res = await client.post("/api/v1/notas/", json=draft_data, headers=headers)
    assert res.status_code == 201
    nota_id = res.json()["id"]
    
    # Verify it is a draft
    res = await client.get(f"/api/v1/notas/expediente/{expediente_id}", headers=headers)
    notas = res.json()
    assert len(notas) == 1
    assert notas[0]["firmada"] is False
    assert notas[0]["es_editable"] is True
    
    # 6. Update Draft
    update_data = {
        "contenido": {"evolucion_y_actualizacion_cuadro": "Dolor severo, requiere observación."},
    }
    res = await client.put(f"/api/v1/notas/{nota_id}", json=update_data, headers=headers)
    assert res.status_code == 200
    
    # 7. Sign Note
    res = await client.post(f"/api/v1/notas/{nota_id}/firmar", headers=headers)
    assert res.status_code == 200
    sign_result = res.json()
    assert sign_result["firmada"] is True
    
    # Verify signature verification endpoint
    res = await client.get(f"/api/v1/notas/{nota_id}/verificar-firma", headers=headers)
    assert res.status_code == 200
    verify_result = res.json()
    assert verify_result["valid"] is True
    
    # Verify note is no longer editable
    res = await client.put(f"/api/v1/notas/{nota_id}", json=update_data, headers=headers)
    assert res.status_code == 403
    
    # 8. Verify Audit Log
    res = await client.get("/api/v1/audit/recent", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    
    # There should be many logs. Let's find some key ones.
    paths = [log["ruta"] for log in logs]
    assert "/api/v1/pacientes/" in paths
    assert f"/api/v1/notas/{nota_id}/firmar" in paths
