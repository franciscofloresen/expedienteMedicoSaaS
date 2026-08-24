"""A malformed tenant context is a 403, never an unhandled 500.

`tenant_uuid` used to be copied into five routers in two versions. The three
signable-document routers (notas, recetas, consentimientos) carried the version
that let the ValueError escape, which API Gateway returns without CORS headers —
so the browser reports a signing failure as a CORS error. That misdiagnosis is
documented as CRIT-04 and already cost this project hours of debugging.

These tests pin the contract for the routers that had the defect.
"""

import uuid

import pytest
from httpx import AsyncClient

# Any syntactically valid UUID works: the tenant check runs before the query.
SOME_ID = str(uuid.uuid4())

MALFORMED_TENANTS = [
    "not-a-uuid",
    "",
    "11111111-1111-1111-1111",  # truncated
]


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/notas/{SOME_ID}/legal-preview",
        "/api/v1/recetas",
        "/api/v1/consentimientos/credenciales-firma",
    ],
)
@pytest.mark.parametrize("tenant", MALFORMED_TENANTS)
async def test_malformed_tenant_is_rejected_without_server_error(
    client: AsyncClient, path: str, tenant: str
) -> None:
    response = await client.get(path, headers={"X-Tenant-ID": tenant})

    assert response.status_code < 500, (
        f"{path} returned {response.status_code} for tenant {tenant!r}; "
        "an unhandled 500 loses the CORS headers and surfaces as a CORS error"
    )
    assert response.status_code in (401, 403)


@pytest.mark.parametrize(
    "path",
    [
        f"/api/v1/notas/{SOME_ID}/legal-preview",
        "/api/v1/recetas",
        "/api/v1/consentimientos/credenciales-firma",
    ],
)
async def test_malformed_tenant_keeps_cors_headers(client: AsyncClient, path: str) -> None:
    """The rejection must still be readable by the browser that triggered it."""
    response = await client.get(
        path,
        headers={"X-Tenant-ID": "not-a-uuid", "Origin": "http://localhost:5173"},
    )

    assert response.status_code in (401, 403)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
