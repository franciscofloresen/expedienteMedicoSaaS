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
async def test_audit_empty_when_no_log_group(client: AsyncClient, seed_tenant_a):
    """Pro tenant, no CloudWatch log group configured (testing) → [] not 500."""
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
    res = await client.get("/api/v1/audit/", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


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
