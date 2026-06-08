import asyncio
import os
import sys

# Add backend directory to python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.paciente import Paciente
from app.models.expediente import Expediente
from app.models.nota import Nota
from app.api.v1.auth import _hash_password
from app.models.tenant_key import TenantKey
from sqlalchemy import text
from datetime import datetime, timezone
import uuid
import json

async def seed_data():
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord")
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            # Create Doctor
            doctor_id = str(uuid.uuid4())
            doctor = Tenant(
                id=doctor_id,
                nombre_medico="Dra. Ana López",
                cedula="MED-12345",
                especialidad="Medicina General",
                email="dr.demo@medrecord.mx",
                password_hash=_hash_password("DemoPassword123!")
            )
            session.add(doctor)
            
            # Local KMS mock key
            random_key = os.urandom(32)
            tenant_key = TenantKey(
                tenant_id=doctor_id,
                encrypted_dek=random_key,
                kms_key_id="mock-local-kms-key",
            )
            session.add(tenant_key)
            
            await session.flush()
            
            # Set context
            await session.execute(
                text(f"SET LOCAL app.current_tenant = '{doctor_id}'")
            )
            
            # Create Patient 1: Carlos Ruiz
            p1_id = str(uuid.uuid4())
            p1 = Paciente(
                id=p1_id,
                tenant_id=doctor_id,
                nombre_completo="Carlos Ruiz González",
                fecha_nacimiento=datetime(1985, 4, 12, tzinfo=timezone.utc),
                sexo="M",
                curp="RUGC850412HDFMNN01",
                telefono="555-019-2837",
                email="carlos.ruiz@example.com",
                creado_por=doctor_id
            )
            session.add(p1)
            await session.flush()
            
            # Create Expediente for Patient 1
            e1_id = str(uuid.uuid4())
            e1 = Expediente(
                id=e1_id,
                tenant_id=doctor_id,
                paciente_id=p1_id,
                folio="EXP-2026-0001",
                creado_por=doctor_id
            )
            session.add(e1)
            await session.flush()
            
            # Create Draft Note for Patient 1
            n1_id = str(uuid.uuid4())
            n1 = Nota(
                id=n1_id,
                tenant_id=doctor_id,
                expediente_id=e1_id,
                tipo_nota="evolucion",
                contenido=json.dumps({"motivo": "Dolor de cabeza", "subjetivo": "Paciente refiere dolor frontal"}, ensure_ascii=False),
                signos_vitales={"pa": "120/80", "fc": 72},
                creado_por=doctor_id,
                es_editable=True
            )
            session.add(n1)
            
            # Create Patient 2: María Elena
            p2_id = str(uuid.uuid4())
            p2 = Paciente(
                id=p2_id,
                tenant_id=doctor_id,
                nombre_completo="María Elena Torres",
                fecha_nacimiento=datetime(1990, 8, 24, tzinfo=timezone.utc),
                sexo="F",
                telefono="555-998-1122",
                creado_por=doctor_id
            )
            session.add(p2)
            
            print(f"Data seeded successfully for doctor: {doctor.email} | password: DemoPassword123!")
            
if __name__ == "__main__":
    asyncio.run(seed_data())
