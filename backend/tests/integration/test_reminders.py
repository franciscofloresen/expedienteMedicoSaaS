import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_reminders_crud(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    # Create
    res = await client.post(
        "/api/v1/reminders/",
        json={
            "title": "Llamar al paciente",
            "description": "Seguimiento post-consulta",
            "remind_at": "2030-01-01T10:00:00Z",
        },
        headers=headers,
    )
    assert res.status_code == 201
    body = res.json()
    reminder_id = body["id"]
    assert body["status"] == "pending"
    assert body["title"] == "Llamar al paciente"

    # List defaults to pending only
    res = await client.get("/api/v1/reminders/", headers=headers)
    assert res.status_code == 200
    ids = [r["id"] for r in res.json()]
    assert reminder_id in ids

    # Dismiss via PATCH
    res = await client.patch(
        f"/api/v1/reminders/{reminder_id}",
        json={"status": "dismissed"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "dismissed"

    # Dismissed reminder no longer in default list
    res = await client.get("/api/v1/reminders/", headers=headers)
    assert reminder_id not in [r["id"] for r in res.json()]

    # ...but visible with include_dismissed=true
    res = await client.get(
        "/api/v1/reminders/?include_dismissed=true", headers=headers
    )
    assert reminder_id in [r["id"] for r in res.json()]

    # Hard delete
    res = await client.delete(f"/api/v1/reminders/{reminder_id}", headers=headers)
    assert res.status_code == 204

    # Deleting again → 404
    res = await client.delete(f"/api/v1/reminders/{reminder_id}", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reminder_remind_at_must_be_future(client: AsyncClient, seed_tenant_a):
    from tests.conftest import TENANT_A_ID

    headers = {"X-Tenant-ID": TENANT_A_ID}

    res = await client.post(
        "/api/v1/reminders/",
        json={"title": "Pasado", "remind_at": "2000-01-01T10:00:00Z"},
        headers=headers,
    )
    assert res.status_code == 422
