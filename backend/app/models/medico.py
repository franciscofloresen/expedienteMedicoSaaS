import uuid
from datetime import datetime
from typing import List

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Medico(Base):
    """Professional identity, decoupled from the consultorio (``tenants``).

    Fase 1 (roadmap §5.1/§6.1): today there is exactly one médico per tenant, but
    modelling it as its own entity avoids binding the professional identity to the
    consultorio and prepares for multiple médicos without forcing advanced roles now.
    Tenant-scoped: RLS ``FORCE`` + ``tenant_isolation_medicos`` policy live in the
    migration (§1.2). Never hard-deleted — deactivate via ``activo`` instead.
    """

    __tablename__ = "medicos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    # Associated identity-provider user (Clerk). Nullable: the backfilled médico of
    # an existing tenant inherits the tenant's identity implicitly for now.
    identity_provider_id: Mapped[str | None] = mapped_column(String(100), index=True)
    nombre_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    rfc: Mapped[str | None] = mapped_column(String(13))
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    credenciales: Mapped[List["MedicoCredencial"]] = relationship(
        "MedicoCredencial", back_populates="medico"
    )


class MedicoCredencial(Base):
    """A professional credential (cédula/especialidad/etc.) belonging to a médico.

    A médico can hold several (general, especialidad, subespecialidad, otra); exactly
    one is the default used to stamp signed documents. Tenant-scoped with its OWN
    ``tenant_id`` (RLS cannot follow the FK to ``medicos`` — §1.2) and ``REVOKE DELETE``:
    a credential used in a signed document is deactivated, never physically removed (§5.1).
    """

    __tablename__ = "medico_credenciales"
    __table_args__ = (
        # Uniqueness of a credential is per-médico on the NORMALIZED number (§5.1).
        Index(
            "uq_credencial_numero_por_medico",
            "medico_id",
            "numero_normalizado",
            unique=True,
        ),
        # At most one default *active* credential per médico (§5.1). Partial unique
        # index → race-proof, and lets an old default be deactivated then replaced.
        Index(
            "uq_credencial_predeterminada_por_medico",
            "medico_id",
            unique=True,
            postgresql_where=text("es_predeterminada AND activa"),
        ),
        Index("ix_medico_credenciales_medico_id", "medico_id"),
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
    medico_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medicos.id"), nullable=False
    )

    numero: Mapped[str] = mapped_column(String(50), nullable=False)
    # Normalized form used for duplicate detection (uppercased, whitespace stripped).
    numero_normalizado: Mapped[str] = mapped_column(String(50), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default="general")
    especialidad: Mapped[str | None] = mapped_column(String(100))
    institucion: Mapped[str | None] = mapped_column(String(200))
    autoridad_emisora: Mapped[str | None] = mapped_column(String(200))
    pais: Mapped[str] = mapped_column(String(2), nullable=False, server_default="MX")
    anio_expedicion: Mapped[int | None] = mapped_column(Integer)

    es_predeterminada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    verificada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    verificada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    medico: Mapped["Medico"] = relationship("Medico", back_populates="credenciales")
