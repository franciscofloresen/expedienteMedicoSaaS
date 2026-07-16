import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Consentimiento(Base):
    __tablename__ = "consentimientos"

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
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedientes.id"), nullable=False, index=True
    )
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1.0")
    plantilla_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consentimiento_plantilla_versiones.id"), index=True
    )
    procedimiento: Mapped[str] = mapped_column(String(200), nullable=False)
    riesgos_principales: Mapped[str | None] = mapped_column(Text)
    contenido_renderizado: Mapped[str] = mapped_column(Text, nullable=False)
    firma_paciente_base64: Mapped[str | None] = mapped_column(Text)
    firmado_paciente_nombre: Mapped[str | None] = mapped_column(String(200))
    firmado_paciente_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    firmado_medico_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hash_contenido: Mapped[str | None] = mapped_column(String(64))
    firma_digital: Mapped[bytes | None] = mapped_column(BYTEA)
    verification_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verification_tokens.id")
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    medico_nombre: Mapped[str | None] = mapped_column(String(200))
    medico_cedula: Mapped[str | None] = mapped_column(String(20))
    medico_especialidad: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
