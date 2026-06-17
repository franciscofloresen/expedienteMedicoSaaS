import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import get_database_url
import uuid

async def main():
    engine = create_async_engine(get_database_url(), echo=True)
    async with engine.begin() as conn:
        try:
            tid = uuid.uuid4()
            await conn.execute(text("SET LOCAL \"app.current_tenant\" = :tid"), {"tid": str(tid)})
            print("SET LOCAL WITH BIND WORKED")
        except Exception as e:
            print("SET LOCAL FAILED:", e)

        try:
            tid = uuid.uuid4()
            await conn.execute(text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tid)})
            print("SELECT SET_CONFIG WORKED")
        except Exception as e:
            print("SELECT SET_CONFIG FAILED:", e)

asyncio.run(main())
