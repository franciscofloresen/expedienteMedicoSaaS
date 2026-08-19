"""Fase 13A — theme preference: roundtrip, allowlist validation, tenant isolation."""

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_A_ID, TENANT_B_ID

pytestmark = pytest.mark.asyncio

_A = {"X-Tenant-ID": TENANT_A_ID}
_B = {"X-Tenant-ID": TENANT_B_ID}


async def test_theme_roundtrip_and_upsert(client: AsyncClient, setup_database) -> None:
    r = await client.put("/api/v1/auth/preferences/theme", json={"tema": "sapphire-dark"}, headers=_A)
    assert r.status_code == 200, r.text
    assert r.json()["tema"] == "sapphire-dark"

    me = await client.get("/api/v1/auth/me", headers=_A)
    assert me.status_code == 200, me.text
    assert me.json()["tema"] == "sapphire-dark"

    # A second write upserts the same single row (no duplicate).
    r2 = await client.put("/api/v1/auth/preferences/theme", json={"tema": "emerald-light"}, headers=_A)
    assert r2.status_code == 200, r2.text
    me2 = await client.get("/api/v1/auth/me", headers=_A)
    assert me2.json()["tema"] == "emerald-light"


async def test_invalid_theme_is_rejected(client: AsyncClient, setup_database) -> None:
    r = await client.put("/api/v1/auth/preferences/theme", json={"tema": "neon-pink"}, headers=_A)
    assert r.status_code == 422


async def test_theme_defaults_and_is_tenant_isolated(client: AsyncClient, setup_database) -> None:
    await client.put("/api/v1/auth/preferences/theme", json={"tema": "plum-dark"}, headers=_A)

    me_b = await client.get("/api/v1/auth/me", headers=_B)
    assert me_b.status_code == 200, me_b.text
    # Tenant B never sees tenant A's preference — RLS + default fallback.
    assert me_b.json()["tema"] == "clinical-teal-dark"
