"""Fase 13 — procedure checklists + adverse events: CRUD, validation, isolation."""

import pytest
from httpx import AsyncClient

from tests.conftest import TENANT_A_ID, TENANT_B_ID

pytestmark = pytest.mark.asyncio

_A = {"X-Tenant-ID": TENANT_A_ID, "X-Plan": "pro"}
_B = {"X-Tenant-ID": TENANT_B_ID, "X-Plan": "pro"}


async def _make_patient(client: AsyncClient, curp: str) -> str:
    res = await client.post(
        "/api/v1/pacientes/",
        json={
            "nombre_completo": "Paciente Proc",
            "sexo": "F",
            "fecha_nacimiento": "1990-01-01",
            "curp": curp,
            "telefono": "555-000-1212",
            "domicilio": "Calle Proc 1",
            "ocupacion": "Diseñadora",
        },
        headers=_A,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def test_checklist_crud_and_toggle(client: AsyncClient, setup_database) -> None:
    pid = await _make_patient(client, "PPPP900101MDFXYZ01")
    res = await client.post(
        "/api/v1/procedimientos/checklists",
        json={
            "paciente_id": pid,
            "momento": "pre",
            "items": [{"texto": "Consentimiento firmado"}, {"texto": "Antisepsia"}],
        },
        headers=_A,
    )
    assert res.status_code == 201, res.text
    chk = res.json()
    cid = chk["id"]
    assert chk["momento"] == "pre"
    assert chk["items"][0]["completado"] is False

    upd = await client.put(
        f"/api/v1/procedimientos/checklists/{cid}",
        json={"items": [{"texto": "Consentimiento firmado", "completado": True}], "observaciones": "OK"},
        headers=_A,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["items"][0]["completado"] is True

    listed = await client.get(f"/api/v1/procedimientos/checklists?paciente_id={pid}", headers=_A)
    assert any(c["id"] == cid for c in listed.json())

    assert (await client.delete(f"/api/v1/procedimientos/checklists/{cid}", headers=_A)).status_code == 204


async def test_checklist_rejects_bad_momento(client: AsyncClient, setup_database) -> None:
    pid = await _make_patient(client, "PPPP900101MDFXYZ02")
    res = await client.post(
        "/api/v1/procedimientos/checklists",
        json={"paciente_id": pid, "momento": "durante", "items": []},
        headers=_A,
    )
    assert res.status_code == 422


async def test_evento_adverso_lifecycle_and_isolation(client: AsyncClient, setup_database) -> None:
    pid = await _make_patient(client, "PPPP900101MDFXYZ03")
    res = await client.post(
        "/api/v1/procedimientos/eventos-adversos",
        json={"paciente_id": pid, "descripcion": "Eritema post-láser", "severidad": "leve"},
        headers=_A,
    )
    assert res.status_code == 201, res.text
    ev = res.json()
    eid = ev["id"]
    assert ev["estado"] == "abierto"

    upd = await client.put(
        f"/api/v1/procedimientos/eventos-adversos/{eid}",
        json={"descripcion": "Eritema post-láser", "severidad": "leve", "estado": "resuelto", "manejo": "Frío local"},
        headers=_A,
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["estado"] == "resuelto"

    # Tenant B cannot see or delete tenant A's event.
    b_list = await client.get(f"/api/v1/procedimientos/eventos-adversos?paciente_id={pid}", headers=_B)
    assert all(e["id"] != eid for e in b_list.json())
    assert (await client.delete(f"/api/v1/procedimientos/eventos-adversos/{eid}", headers=_B)).status_code == 404
