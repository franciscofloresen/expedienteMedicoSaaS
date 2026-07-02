import asyncio

from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import async_session_maker
from app.main import app


async def main():
    async with async_session_maker() as db:
        res = await db.execute(text("SELECT id FROM tenants LIMIT 1"))
        tenant_id = res.scalar()
        res2 = await db.execute(text("SELECT id FROM notas LIMIT 1"))
        nota_id = res2.scalar()

    print(f"Tenant: {tenant_id}, Nota: {nota_id}")

    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock Clerk auth
        response = await client.post(
            "/api/v1/recetas",
            json={
                "nota_id": str(nota_id),
                "medicamentos": [{"descripcion": "Ibuprofeno"}],
                "indicaciones_generales": "Tomar 1 cada 8 hrs"
            },
            headers={"Authorization": "Bearer test_token"} # Note: testing auth might fail if it really verifies Clerk
        )
        print("Status:", response.status_code)
        print("Response:", response.text)

if __name__ == "__main__":
    asyncio.run(main())
