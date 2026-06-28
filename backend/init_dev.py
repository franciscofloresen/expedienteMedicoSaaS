import asyncio

from sqlalchemy import select, text

from app.db.session import _get_session_factory
from app.models.tenant import Tenant


async def create_dev_tenant():
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            # Bypass RLS to insert tenant
            await session.execute(
                text(
                    "SET LOCAL \"app.current_tenant\" = '00000000-0000-0000-0000-000000000000'"
                )
            )

            tenant_id = "00000000-0000-0000-0000-000000000000"

            # Check if tenant exists
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                print("Creando tenant de desarrollo...")
                t = Tenant(
                    id=tenant_id,
                    nombre_medico="Dr. Dev",
                    cedula="DEV12345",
                    email="dev@local.host",
                )
                session.add(t)
            else:
                print("Tenant de desarrollo ya existe.")


if __name__ == "__main__":
    asyncio.run(create_dev_tenant())
