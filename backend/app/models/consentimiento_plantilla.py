"""Versioned, shared consent-template catalog (Fase 4).

The catalog is shared reference data, like ``cie10``: it intentionally has no
``tenant_id`` and therefore no tenant RLS policy. Runtime sessions receive SELECT only;
publication is performed by the audited admin payload.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ConsentimientoPlantilla(Base):
    __tablename__ = "consentimiento_plantillas"
    __table_args__ = (
        CheckConstraint("estado IN ('activa', 'retirada')", name="plantilla_estado_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    template_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    categoria: Mapped[str] = mapped_column(String(80), nullable=False)
    especialidad: Mapped[str | None] = mapped_column(String(100), index=True)
    procedimiento: Mapped[str | None] = mapped_column(String(160), index=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="activa")
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ConsentimientoPlantillaVersion(Base):
    __tablename__ = "consentimiento_plantilla_versiones"
    __table_args__ = (
        UniqueConstraint("plantilla_id", "version", name="uq_plantilla_version"),
        CheckConstraint(
            "estado IN ('borrador', 'publicada', 'retirada')",
            name="plantilla_version_estado_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    plantilla_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("consentimiento_plantillas.id"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    contenido: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    campos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    firmas_requeridas: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    referencias_normativas: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="borrador")
    responsable_revision: Mapped[str | None] = mapped_column(String(200))
    revisada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contenido_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    publicada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
