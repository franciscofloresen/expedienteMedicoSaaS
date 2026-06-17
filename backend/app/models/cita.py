import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class Cita(Base):
    __tablename__ = "citas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=True, index=True
    )
    
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    # Estados: "Programada", "Cancelada", "Completada"
    estado: Mapped[str] = mapped_column(String(50), server_default="Programada")
    notas: Mapped[str | None] = mapped_column(Text)
    
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id], back_populates="citas")
    paciente: Mapped["Paciente"] = relationship("Paciente", foreign_keys=[paciente_id], back_populates="citas")
