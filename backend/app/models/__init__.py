from .audit_log import AuditLog
from .base import Base
from .cie10 import CIE10
from .cita import Cita
from .expediente import Expediente
from .nota import Nota
from .paciente import Paciente
from .receta import Receta
from .reminder import Reminder
from .tenant import Tenant

# Import all models here so Alembic can discover them
__all__ = [
    "Base",
    "AuditLog",
    "Tenant",
    "Paciente",
    "Expediente",
    "Nota",
    "Cita",
    "CIE10",
    "Receta",
    "Reminder",
]
