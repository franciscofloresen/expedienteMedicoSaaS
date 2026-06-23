import asyncio

from sqlalchemy import text

from app.db.session import _get_session_factory


async def main():
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            res = await session.execute(
                text(
                    "SELECT id FROM tenants WHERE id = '00000000-0000-0000-0000-000000000000'"
                )
            )
            if not res.scalar():
                print("Inserting dummy tenant...")
                await session.execute(
                    text(
                        """
                    INSERT INTO tenants (id, nombre_medico, cedula, email)
                    VALUES (
                        '00000000-0000-0000-0000-000000000000',
                        'Dr. Local Dev',
                        'DEV-000',
                        'dev@local.host'
                    )
                """
                    )
                )
                await session.execute(
                    text(
                        """
                    INSERT INTO tenant_keys (tenant_id, dek_encrypted)
                    VALUES ('00000000-0000-0000-0000-000000000000', 'dummy_dek_for_local_dev')
                """
                    )
                )
            else:
                print("Dummy tenant already exists")


asyncio.run(main())
