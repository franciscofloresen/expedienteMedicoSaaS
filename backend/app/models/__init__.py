from .audit_log import AuditLog
from .base import Base
from .cie10 import CIE10
from .cita import Cita
from .clinical_file import ClinicalFile, TenantStorageUsage
from .consentimiento import Consentimiento
from .encuentro import EncuentroClinico
from .expediente import Expediente
from .medico import Medico, MedicoCredencial
from .message_log import MessageLog
from .nota import Nota
from .nota_diagnostico import NotaDiagnostico
from .paciente import Paciente
from .receta import Receta
from .reminder import Reminder
from .tenant import Tenant
from .verification_token import VerificationToken

# Import all models here so Alembic can discover them
__all__ = [
    "Base",
    "AuditLog",
    "Tenant",
    "Paciente",
    "Expediente",
    "Nota",
    "NotaDiagnostico",
    "Consentimiento",
    "EncuentroClinico",
    "VerificationToken",
    "MessageLog",
    "Cita",
    "CIE10",
    "Receta",
    "Reminder",
    "ClinicalFile",
    "TenantStorageUsage",
    "Medico",
    "MedicoCredencial",
]
