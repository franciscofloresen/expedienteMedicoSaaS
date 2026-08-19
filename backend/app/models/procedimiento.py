import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProcedimientoChecklist(Base):
    """A pre- or post-procedure checklist (Fase 13). Working clinical-workflow
    record the doctor edits over time — keeps DELETE/UPDATE, no immutability.
    Tenant-scoped; RLS FORCE + policy in the migration."""

    __tablename__ = "procedimiento_checklists"
    __table_args__ = (
        CheckConstraint("momento IN ('pre', 'post')", name="procedimiento_checklists_momento_check"),
        Index("ix_procedimiento_checklists_tenant_pac", "tenant_id", "paciente_id"),
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
    encuentro_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encuentros_clinicos.id")
    )
    momento: Mapped[str] = mapped_column(String(10), nullable=False)
    items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    observaciones: Mapped[str | None] = mapped_column(Text)

    creado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class EventoAdverso(Base):
    """Adverse-event tracking (Fase 13). Editable follow-up record with severity and
    open/resolved state. Tenant-scoped; RLS FORCE + policy in the migration."""

    __tablename__ = "eventos_adversos"
    __table_args__ = (
        CheckConstraint(
            "severidad IN ('leve', 'moderado', 'grave')", name="eventos_adversos_severidad_check"
        ),
        CheckConstraint("estado IN ('abierto', 'resuelto')", name="eventos_adversos_estado_check"),
        Index("ix_eventos_adversos_tenant_pac", "tenant_id", "paciente_id"),
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
    encuentro_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encuentros_clinicos.id")
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    severidad: Mapped[str] = mapped_column(String(10), nullable=False, server_default="leve")
    fecha: Mapped[date | None] = mapped_column(Date)
    manejo: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(10), nullable=False, server_default="abierto")

    creado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
