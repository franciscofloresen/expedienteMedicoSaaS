import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotaPlantilla(Base):
    """A configurable note template (Fase 13): a versioned JSON of field pre-fills
    that seeds the note editor (motivo / exploración / plan / diagnóstico).

    Editable preference, not clinical evidence — keeps DELETE/UPDATE, no immutability
    trigger. Tenant-scoped with its own ``tenant_id``; RLS ``FORCE`` +
    ``tenant_isolation_nota_plantillas`` policy live in the migration. ``version``
    bumps on edit so a template change is traceable.
    """

    __tablename__ = "nota_plantillas"
    __table_args__ = (Index("ix_nota_plantillas_tenant", "tenant_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    campos: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
