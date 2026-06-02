from .base import Base
from .tenant import Tenant
from .tenant_key import TenantKey
from .paciente import Paciente
from .expediente import Expediente
from .nota import Nota
from .consentimiento import Consentimiento
from .aviso_privacidad import AvisoPrivacidad
from .audit import AuditLog

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
]
