from .base import Base
from .cita import Cita
from .expediente import Expediente
from .nota import Nota
from .paciente import Paciente
from .tenant import Tenant

# Import all models here so Alembic can discover them
__all__ = [
    "Base",
    "Tenant",
    "Paciente",
    "Expediente",
    "Nota",
    "Cita",
]
