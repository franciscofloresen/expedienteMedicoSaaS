import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FotografiaClinica(Base):
    """Clinical-photo metadata sidecar over a ``clinical_files`` object (Fase 13).

    The image bytes live in the clinical-file S3 pipeline; this row adds only
    descriptive metadata + an optional link to the specific consent, and a
    free-text ``grupo_comparacion`` to pair before/after photos. No biometrics.
    Tenant-scoped; RLS FORCE + policy in the migration.
    """

    __tablename__ = "fotografias_clinicas"
    __table_args__ = (
        CheckConstraint(
            "categoria IN ('antes', 'despues', 'seguimiento', 'general')",
            name="fotografias_clinicas_categoria_check",
        ),
        CheckConstraint(
            "lateralidad IS NULL OR lateralidad IN ('izquierda', 'derecha', 'bilateral', 'na')",
            name="fotografias_clinicas_lateralidad_check",
        ),
        Index("ix_fotografias_clinicas_tenant_pac", "tenant_id", "paciente_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=False
    )
    clinical_file_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_files.id"), nullable=False, unique=True
    )
    consentimiento_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consentimientos.id")
    )
    categoria: Mapped[str] = mapped_column(String(30), nullable=False, server_default="general")
    lateralidad: Mapped[str | None] = mapped_column(String(15))
    zona_anatomica: Mapped[str | None] = mapped_column(String(120))
    fecha_toma: Mapped[date | None] = mapped_column(Date)
    grupo_comparacion: Mapped[str | None] = mapped_column(String(80))

    creado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
