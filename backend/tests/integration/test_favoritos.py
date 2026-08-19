"""Fase 13 — médico favoritos: CRUD + tenant isolation (RLS)."""

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_A_ID, TENANT_B_ID

pytestmark = pytest.mark.asyncio

_A = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
_B = {"X-Tenant-ID": TENANT_B_ID, "X-Plan": "pro"}


async def test_favoritos_crud(client: AsyncClient, setup_database) -> None:
    res = await client.post(
        "/api/v1/favoritos/",
        json={"kind": "receta", "label": "Paracetamol", "texto": "Paracetamol 500 mg c/8h x3d"},
        headers=_A,
    )
    assert res.status_code == 201, res.text
    fav = res.json()
    fid = fav["id"]
    assert fav["kind"] == "receta"

    # Filtered listing returns it under its kind, not under another.
    receta = await client.get("/api/v1/favoritos/?kind=receta", headers=_A)
    assert any(f["id"] == fid for f in receta.json())
    plan = await client.get("/api/v1/favoritos/?kind=plan", headers=_A)
    assert all(f["id"] != fid for f in plan.json())

    # Editable (not immutable): update its text.
    upd = await client.put(
        f"/api/v1/favoritos/{fid}",
        json={"label": "Paracetamol", "texto": "Paracetamol 500 mg c/6h"},
        headers=_A,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["texto"] == "Paracetamol 500 mg c/6h"

    # Deletable.
    dele = await client.delete(f"/api/v1/favoritos/{fid}", headers=_A)
    assert dele.status_code == 204
    after = await client.get("/api/v1/favoritos/", headers=_A)
    assert all(f["id"] != fid for f in after.json())


async def test_favoritos_rejects_unknown_kind(client: AsyncClient, setup_database) -> None:
    res = await client.post(
        "/api/v1/favoritos/",
        json={"kind": "no_existe", "label": "x", "texto": "y"},
        headers=_A,
    )
    assert res.status_code == 422


async def test_favoritos_are_tenant_isolated(client: AsyncClient, setup_database) -> None:
    res = await client.post(
        "/api/v1/favoritos/",
        json={"kind": "plan", "label": "Plan A", "texto": "Control en 2 semanas"},
        headers=_A,
    )
    assert res.status_code == 201, res.text
    fid = res.json()["id"]

    # Tenant B cannot see tenant A's favorite...
    b_list = await client.get("/api/v1/favoritos/", headers=_B)
    assert all(f["id"] != fid for f in b_list.json())

    # ...nor delete it (RLS hides the row → 404, not 204).
    b_del = await client.delete(f"/api/v1/favoritos/{fid}", headers=_B)
    assert b_del.status_code == 404
