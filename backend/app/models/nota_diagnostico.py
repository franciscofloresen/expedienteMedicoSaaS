import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotaDiagnostico(Base):
    """A structured CIE-10 diagnosis attached to a clinical note.

    Fase 3 (roadmap §5.3): replaces the single free-text ``notas.diagnostico_cie10``
    with multiple, ordered, coded diagnoses per note. The link points **at** the note
    (``nota_id``); a signed note is immutable (NOM-004 trigger), so a diagnosis is only
    ever written when the note is created and the note itself is never UPDATEd (§1.1).

    Snapshot fields (``descripcion_snapshot`` / ``version_snapshot``) freeze the catalog
    text/version at recording time, so a later catalog revision never rewrites history.

    Tenant-scoped with its OWN ``tenant_id`` (RLS cannot follow FKs — §1.2): RLS
    ``FORCE`` + ``tenant_isolation_nota_diagnosticos`` policy and ``REVOKE DELETE`` +
    ``prevent_nota_diagnosticos_deletion`` trigger live in the migration. A single
    principal diagnosis per note is enforced by the partial unique index
    ``uq_nota_diagnostico_principal`` (race-proof, §5.3).
    """

    __tablename__ = "nota_diagnosticos"
    __table_args__ = (
        CheckConstraint(
            "certeza IN ('confirmado', 'presuntivo', 'descartado')",
            name="nota_diagnosticos_certeza_check",
        ),
        # One principal diagnosis per note (§5.3): partial unique index → race-proof.
        Index(
            "uq_nota_diagnostico_principal",
            "nota_id",
            unique=True,
            postgresql_where=text("es_principal"),
        ),
        Index("ix_nota_diagnosticos_nota", "tenant_id", "nota_id"),
        Index("ix_nota_diagnosticos_cie10_code", "cie10_code"),
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
    nota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notas.id", name="fk_nota_diagnostico_nota"),
        nullable=False,
    )
    cie10_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("cie10.code", name="fk_nota_diagnostico_cie10"),
        nullable=False,
    )

    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    es_principal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    certeza: Mapped[str] = mapped_column(String(20), nullable=False, server_default="presuntivo")

    descripcion_snapshot: Mapped[str | None] = mapped_column(String(500))
    version_snapshot: Mapped[str | None] = mapped_column(String(50))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
