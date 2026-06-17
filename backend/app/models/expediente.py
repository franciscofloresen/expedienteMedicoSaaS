import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.models.nota import Nota
    from app.models.paciente import Paciente

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Expediente(Base):
    __tablename__ = "expedientes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "folio", name="uq_folio_tenant"),
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
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=False, index=True
    )
    folio: Mapped[str] = mapped_column(String(20), nullable=False)

    # Clinical history — encrypted JSON
    antecedentes_cifrado: Mapped[bytes | None] = mapped_column(BYTEA)

    estado: Mapped[str] = mapped_column(String(20), server_default="activo")

    # Audit
    creado_por: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    paciente: Mapped["Paciente"] = relationship(
        "Paciente", back_populates="expedientes"
    )
    notas: Mapped[List["Nota"]] = relationship(
        "Nota", back_populates="expediente"
    )
