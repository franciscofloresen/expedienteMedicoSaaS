import asyncio

from app.db.session import _get_session_factory
from app.models.cie10 import CIE10

# Minimal seed for Beta
TOP_CIE10 = [
    {"code": "J00", "description": "Rinofaringitis aguda (resfriado común)", "category": "Respiratorio"},
    {"code": "J06.9", "description": "Infección aguda de las vías respiratorias superiores, no especificada", "category": "Respiratorio"},
    {"code": "E11.9", "description": "Diabetes mellitus tipo 2 sin complicaciones", "category": "Endocrino"},
    {"code": "I10", "description": "Hipertensión esencial (primaria)", "category": "Cardiovascular"},
    {"code": "A09", "description": "Diarrea y gastroenteritis de presunto origen infeccioso", "category": "Gastrointestinal"},
    {"code": "N39.0", "description": "Infección de vías urinarias, sitio no especificado", "category": "Genitourinario"},
]

async def seed_cie10():
    factory = _get_session_factory()
    async with factory() as session:
        for item in TOP_CIE10:
            cie10 = CIE10(**item)
            await session.merge(cie10)
        await session.commit()
        print(f"Seeded {len(TOP_CIE10)} CIE-10 codes successfully.")

if __name__ == "__main__":
    asyncio.run(seed_cie10())
