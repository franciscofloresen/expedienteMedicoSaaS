import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_terms_acceptance_flow(client: AsyncClient, seed_tenant_b):
    """status → accept → status → idempotent re-accept."""
    from tests.conftest import TENANT_B_ID

    headers = {"X-Tenant-ID": TENANT_B_ID}

    # Initially not accepted
    res = await client.get("/api/v1/auth/terms-status", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is False
    assert body["accepted_at"] is None
    assert body["version"] is None

    # Accept
    res = await client.post(
        "/api/v1/auth/accept-terms", json={"version": "v1.0"}, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["accepted"] is True
    first_accepted_at = res.json()["accepted_at"]
    assert first_accepted_at is not None

    # Status reflects acceptance
    res = await client.get("/api/v1/auth/terms-status", headers=headers)
    body = res.json()
    assert body["accepted"] is True
    assert body["version"] == "v1.0"
    assert body["accepted_at"] is not None

    # Idempotent — accepting again does not error, updates version/timestamp
    res = await client.post(
        "/api/v1/auth/accept-terms", json={"version": "v2.0"}, headers=headers
    )
    assert res.status_code == 200
    assert res.json()["accepted"] is True

    res = await client.get("/api/v1/auth/terms-status", headers=headers)
    assert res.json()["version"] == "v2.0"
