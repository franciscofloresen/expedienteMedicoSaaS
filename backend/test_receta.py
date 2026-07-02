import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.receta import Receta


async def main():
    # Use standard local db connection
    uri = settings.database_url
    engine = create_async_engine(uri)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Need a valid tenant and nota
    async with async_session() as db:
        # Get random tenant
        res = await db.execute(text("SELECT id FROM tenants LIMIT 1"))
        tenant_id = res.scalar()
        if not tenant_id:
            print("No tenant")
            return

        res2 = await db.execute(text("SELECT id FROM notas LIMIT 1"))
        nota_id = res2.scalar()
        if not nota_id:
            print("No nota")
            return

        print(f"Using tenant: {tenant_id}, nota: {nota_id}")

        receta = Receta(
            tenant_id=tenant_id,
            nota_id=nota_id,
            medicamentos=[{"descripcion": "Test"}],
            indicaciones_generales="Test ind"
        )
        db.add(receta)
        try:
            await db.commit()
            await db.refresh(receta)
            print("Success:", receta.id)
        except Exception as e:
            print("Error:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())
