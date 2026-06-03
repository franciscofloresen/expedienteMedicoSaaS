import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import _get_session_factory
from app.models.tenant import Tenant
from app.models.tenant_key import TenantKey
from sqlalchemy import select, text
import uuid

async def create_dev_tenant():
    factory = _get_session_factory()
    async with factory() as session:
        async with session.begin():
            # Bypass RLS to insert tenant
            await session.execute(text("SET LOCAL \"app.current_tenant\" = '00000000-0000-0000-0000-000000000000'"))
            
            tenant_id = "00000000-0000-0000-0000-000000000000"
            
            # Check if tenant exists
            stmt = select(Tenant).where(Tenant.id == tenant_id)
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                print("Creando tenant de desarrollo...")
                t = Tenant(id=tenant_id, nombre_medico="Dr. Dev", cedula="DEV12345", email="dev@local.host")
                session.add(t)
                
                # Check if key exists
                stmt_k = select(TenantKey).where(TenantKey.tenant_id == tenant_id)
                res_k = await session.execute(stmt_k)
                if not res_k.scalar_one_or_none():
                    print("Creando llave de cifrado de desarrollo...")
                    # Cifrado falso solo para pruebas
                    tk = TenantKey(tenant_id=tenant_id, encrypted_dek=b"mock_encrypted_dek", kms_key_id="mock_kms_key")
                    session.add(tk)
            else:
                print("Tenant de desarrollo ya existe.")

if __name__ == "__main__":
    asyncio.run(create_dev_tenant())
