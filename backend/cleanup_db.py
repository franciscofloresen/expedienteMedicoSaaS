import asyncio
from sqlalchemy import text
from app.db.session import _get_session_factory

async def main():
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            await session.execute(text("DELETE FROM notas"))
            await session.execute(text("DELETE FROM expedientes"))
            await session.execute(text("DELETE FROM pacientes"))
            print("Deleted all records from tables to avoid decryption errors.")

asyncio.run(main())
