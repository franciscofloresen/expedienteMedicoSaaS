"""Fase 13 — note templates: CRUD, version bump, field limits, tenant isolation."""

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_A_ID, TENANT_B_ID

pytestmark = pytest.mark.asyncio

_A = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
_B = {"X-Tenant-ID": TENANT_B_ID, "X-Plan": "pro"}


async def test_plantilla_crud_and_version_bump(client: AsyncClient, setup_database) -> None:
    res = await client.post(
        "/api/v1/plantillas-nota/",
        json={
            "nombre": "Dermatoscopia",
            "campos": {
                "exploracion_fisica": "Lesión pigmentada, bordes...",
                "plan_tratamiento": "Control fotográfico en 3 meses.",
            },
        },
        headers=_A,
    )
    assert res.status_code == 201, res.text
    tpl = res.json()
    tid = tpl["id"]
    assert tpl["version"] == 1
    assert tpl["campos"]["exploracion_fisica"].startswith("Lesión")

    listed = await client.get("/api/v1/plantillas-nota/", headers=_A)
    assert any(t["id"] == tid for t in listed.json())

    # Editing bumps the version (traceable change).
    upd = await client.put(
        f"/api/v1/plantillas-nota/{tid}",
        json={"nombre": "Dermatoscopia", "campos": {"plan_tratamiento": "Control en 1 mes."}},
        headers=_A,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["version"] == 2
    assert "exploracion_fisica" not in upd.json()["campos"]

    dele = await client.delete(f"/api/v1/plantillas-nota/{tid}", headers=_A)
    assert dele.status_code == 204


async def test_plantilla_rejects_unknown_field(client: AsyncClient, setup_database) -> None:
    """`campos` is limited to known note fields — not a generic form builder."""
    res = await client.post(
        "/api/v1/plantillas-nota/",
        json={"nombre": "x", "campos": {"campo_arbitrario": "boom"}},
        headers=_A,
    )
    assert res.status_code == 422


async def test_plantillas_are_tenant_isolated(client: AsyncClient, setup_database) -> None:
    res = await client.post(
        "/api/v1/plantillas-nota/",
        json={"nombre": "Solo A", "campos": {"motivo_consulta": "Control"}},
        headers=_A,
    )
    assert res.status_code == 201, res.text
    tid = res.json()["id"]

    b_list = await client.get("/api/v1/plantillas-nota/", headers=_B)
    assert all(t["id"] != tid for t in b_list.json())

    b_del = await client.delete(f"/api/v1/plantillas-nota/{tid}", headers=_B)
    assert b_del.status_code == 404
