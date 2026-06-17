import asyncio
from sqlalchemy import text
from app.db.session import _get_session_factory

async def main():
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            # 32 byte key
            valid_32_byte_key = b"dummy_dek_for_local_dev_12345678"
            await session.execute(text("""
                UPDATE tenant_keys 
                SET encrypted_dek = :key, kms_key_id = 'dummy-kms'
                WHERE tenant_id = '00000000-0000-0000-0000-000000000000'
            """), {"key": valid_32_byte_key})
            
            # If not updated, insert it
            res = await session.execute(text("SELECT tenant_id FROM tenant_keys WHERE tenant_id = '00000000-0000-0000-0000-000000000000'"))
            if not res.scalar():
                await session.execute(text("""
                    INSERT INTO tenant_keys (tenant_id, encrypted_dek, kms_key_id)
                    VALUES ('00000000-0000-0000-0000-000000000000', :key, 'dummy-kms')
                """), {"key": valid_32_byte_key})
                
            print("DEK updated to exactly 32 bytes.")

asyncio.run(main())
