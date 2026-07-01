import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.expediente import Expediente

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Nota(Base):
    __tablename__ = "notas"
    __table_args__ = (
        CheckConstraint(
            "tipo_nota IN ('ingreso', 'evolucion', 'egreso', 'interconsulta', "
            "'referencia', 'traslado', 'quirurgica', 'anestesiologia', "
            "'enfermeria', 'urgencias', 'historia_clinica')",
            name="notas_tipo_nota_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedientes.id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    tipo_nota: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostico_cie10: Mapped[str | None] = mapped_column(String(255))

    # Encounter fields
    motivo_consulta: Mapped[str | None] = mapped_column(Text)
    exploracion_fisica: Mapped[str | None] = mapped_column(Text)
    plan_tratamiento: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), server_default="draft")

    signos_vitales: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Signature
    firma_digital: Mapped[bytes | None] = mapped_column(BYTEA)
    firma_hash_contenido: Mapped[str | None] = mapped_column(String(64))
    firma_kms_key_id: Mapped[str | None] = mapped_column(String(200))
    firma_algoritmo: Mapped[str | None] = mapped_column(
        String(30), server_default="ECDSA_SHA_256"
    )
    firmado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    firmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    es_editable: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # Snapshot metadata
    medico_nombre: Mapped[str | None] = mapped_column(String(200))
    medico_cedula: Mapped[str | None] = mapped_column(String(20))
    medico_especialidad: Mapped[str | None] = mapped_column(String(100))

    # Audit
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )

    expediente: Mapped["Expediente"] = relationship(
        "Expediente", back_populates="notas"
    )
