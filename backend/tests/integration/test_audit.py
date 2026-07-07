import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_audit_forbidden_for_basico(client: AsyncClient, seed_tenant_a):
    """Audit log is a Pro-only feature — Básico gets 403."""
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}  # no X-Plan → defaults to basico
    res = await client.get("/api/v1/audit/", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_audit_records_and_returns_writes(client: AsyncClient, seed_tenant_a):
    """A write is recorded in the bitácora and readable by a Pro tenant."""
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}

    # A write — the audit middleware should append a row.
    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Auditoría",
            "sexo": "M",
            "fecha_nacimiento": "1980-02-02",
        },
        headers=headers,
    )
    assert res.status_code == 201

    # Read the bitácora back.
    res = await client.get("/api/v1/audit/?limit=200", headers=headers)
    assert res.status_code == 200
    entries = res.json()
    assert isinstance(entries, list)
    assert any(
        e["action"] == "POST /api/v1/pacientes/" and e["status_code"] == 201
        for e in entries
    )


@pytest.mark.asyncio
async def test_audit_pagination_params(client: AsyncClient, seed_tenant_a):
    """limit/offset are accepted and validated (Pro tenant)."""
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}

    res = await client.get("/api/v1/audit/?limit=10&offset=5", headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Out-of-range limit is rejected by validation
    res = await client.get("/api/v1/audit/?limit=9999", headers=headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_audit_requires_tenant(client: AsyncClient, seed_tenant_a):
    """No tenant context → 401 from tenant middleware."""
    res = await client.get("/api/v1/audit/")
    assert res.status_code == 401
