import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.models.cita import Cita
    from app.models.expediente import Expediente
    from app.models.tenant import Tenant

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Paciente(Base):
    __tablename__ = "pacientes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "curp", name="uq_paciente_tenant"),
        CheckConstraint("sexo IN ('M', 'F', 'X')", name="pacientes_sexo_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # NOM-004 required
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    sexo: Mapped[str] = mapped_column(String(10), nullable=False)

    # Optional
    curp: Mapped[str | None] = mapped_column(String(18), index=True)
    entidad_nacimiento: Mapped[str | None] = mapped_column(String(50))
    nacionalidad: Mapped[str | None] = mapped_column(
        String(50), server_default="Mexicana"
    )
    ocupacion: Mapped[str | None] = mapped_column(String(100))

    # Contact
    telefono: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))

    # Insurance
    aseguradora: Mapped[str | None] = mapped_column(String(100))
    num_poliza: Mapped[str | None] = mapped_column(String(50))

    # Medical / Emergency
    contacto_emergencia: Mapped[str | None] = mapped_column(String(200))
    telefono_emergencia: Mapped[str | None] = mapped_column(String(20))
    tipo_sangre: Mapped[str | None] = mapped_column(String(5))
    alergias: Mapped[str | None] = mapped_column(Text)

    # Encrypted fields
    domicilio_cifrado: Mapped[bytes | None] = mapped_column(BYTEA)

    # Soft delete (NOM-004 requires 5-year retention)
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    # Audit
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", foreign_keys=[tenant_id], back_populates="pacientes"
    )
    expedientes: Mapped[List["Expediente"]] = relationship(
        "Expediente", back_populates="paciente"
    )
    citas: Mapped[List["Cita"]] = relationship(
        "Cita", foreign_keys="Cita.paciente_id", back_populates="paciente"
    )
