import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, Column, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    nombre_medico: Mapped[str] = mapped_column(String(200), nullable=False)
    cedula: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    especialidad: Mapped[str | None] = mapped_column(String(100))
    rfc: Mapped[str | None] = mapped_column(String(13))
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    plan: Mapped[str] = mapped_column(String(20), server_default="basico")
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Relationships
    tenant_key: Mapped["TenantKey"] = relationship("TenantKey", back_populates="tenant", uselist=False)
    pacientes: Mapped[List["Paciente"]] = relationship("Paciente", back_populates="tenant")
