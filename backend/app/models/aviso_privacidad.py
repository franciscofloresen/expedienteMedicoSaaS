import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AvisoPrivacidad(Base):
    __tablename__ = "avisos_privacidad"
    __table_args__ = (UniqueConstraint("tenant_id", "paciente_id", "version_aviso"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=False, index=True
    )

    version_aviso: Mapped[str] = mapped_column(String(10), server_default="1.0")
    aceptado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    consentimiento_datos_sensibles: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false")
    )
