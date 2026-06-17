from .audit import AuditLog
from .aviso_privacidad import AvisoPrivacidad
from .base import Base
from .cita import Cita
from .consentimiento import Consentimiento
from .expediente import Expediente
from .nota import Nota
from .paciente import Paciente
from .tenant import Tenant
from .tenant_key import TenantKey

# Import all models here so Alembic can discover them
__all__ = [
    "Base",
    "Tenant",
    "TenantKey",
    "Paciente",
    "Expediente",
    "Nota",
    "Consentimiento",
    "AvisoPrivacidad",
    "AuditLog",
    "Cita",
]
