from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.api.v1 import files as files_api
from app.core.config import settings
from tests.conftest import TENANT_A_ID, TENANT_B_ID


@pytest.mark.asyncio
async def test_basico_has_no_file_storage(client: AsyncClient, seed_tenant_a):
    headers = {"X-Tenant-ID": TENANT_A_ID}
    usage = await client.get("/api/v1/files/usage", headers=headers)
    assert usage.status_code == 200
    assert usage.json()["quota_bytes"] == 0

    response = await client.post(
        f"/api/v1/files/expedientes/{uuid4()}/upload-url",
        headers=headers,
        json={
            "filename": "resultado.pdf",
            "content_type": "application/pdf",
            "size_bytes": 1024,
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pro_upload_completion_and_tenant_isolation(
    client: AsyncClient, seed_tenant_a, seed_tenant_b, monkeypatch
):
    headers_a = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
    patient = await client.post(
        "/api/v1/pacientes/",
        headers=headers_a,
        json={
            "nombre_completo": "Paciente Archivo Seguro",
            "sexo": "X",
            "fecha_nacimiento": "1990-01-01",
        },
    )
    assert patient.status_code == 201
    expediente = await client.post(
        "/api/v1/expedientes/",
        headers=headers_a,
        json={"paciente_id": patient.json()["id"]},
    )
    assert expediente.status_code == 201
    expediente_id = expediente.json()["id"]

    monkeypatch.setattr(
        files_api,
        "create_upload_post",
        lambda **_: {"url": "https://s3.example/upload", "fields": {"policy": "test"}},
    )

    upload = await client.post(
        f"/api/v1/files/expedientes/{expediente_id}/upload-url",
        headers=headers_a,
        json={
            "filename": "radiografia.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 2048,
            "category": "xray",
        },
    )
    assert upload.status_code == 201
    file_id = upload.json()["file_id"]

    def fake_head(s3_key: str):
        assert file_id in s3_key
        return {
            "ContentLength": 2048,
            "ServerSideEncryption": "aws:kms",
            "VersionId": "version-1",
            "Metadata": {"file-id": file_id, "tenant-id": TENANT_A_ID},
        }

    monkeypatch.setattr(files_api, "head_uploaded_object", fake_head)
    monkeypatch.setattr(settings, "malware_scan_required", False)
    completed = await client.post(f"/api/v1/files/{file_id}/complete", headers=headers_a)
    assert completed.status_code == 200
    assert completed.json()["status"] == "available"

    usage = await client.get("/api/v1/files/usage", headers=headers_a)
    assert usage.json()["used_bytes"] == 2048
    assert usage.json()["reserved_bytes"] == 0

    own_files = await client.get(f"/api/v1/files/expedientes/{expediente_id}", headers=headers_a)
    assert [item["id"] for item in own_files.json()] == [file_id]

    headers_b = {"X-Tenant-ID": TENANT_B_ID, "X-Plan": "pro"}
    other_files = await client.get(f"/api/v1/files/expedientes/{expediente_id}", headers=headers_b)
    assert other_files.status_code == 200
    assert other_files.json() == []
