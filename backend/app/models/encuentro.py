import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EncuentroClinico(Base):
    """A real clinical encounter (atención), distinct from the agenda (``citas``).

    Fase 2 (roadmap §5.2/§6.3): a cita is a scheduled slot; an encuentro is the
    attention that actually happened. Separating them stops a cancelled cita from
    ever being counted as a first consultation. The "primera vez / subsecuente"
    rule is enforced by a **partial unique index** (one completed ``primera_vez``
    per patient per tenant), not transactional validation (§3) — race-proof.

    Tenant-scoped with its OWN ``tenant_id`` (RLS cannot follow FKs — §1.2): RLS
    ``FORCE`` + ``tenant_isolation_encuentros_clinicos`` policy and ``REVOKE DELETE``
    + ``prevent_encuentros_clinicos_deletion`` trigger live in the migration.

    The link to the initial note lives **on the encounter side**
    (``nota_inicial_id``): a signed nota is immutable (NOM-004 trigger), so we never
    UPDATE it to attach an encounter (§1.1). New notas carry
    ``notas.encuentro_clinico_id`` written only at creation.
    """

    __tablename__ = "encuentros_clinicos"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('primera_vez', 'subsecuente', 'procedimiento', 'urgencia', 'otro')",
            name="encuentros_clinicos_tipo_check",
        ),
        CheckConstraint(
            "estado IN ('programado', 'iniciado', 'completado', 'cancelado')",
            name="encuentros_clinicos_estado_check",
        ),
        CheckConstraint(
            "clasificacion_origen IN ('automatica', 'manual', 'migracion')",
            name="encuentros_clinicos_clasificacion_origen_check",
        ),
        # Enforcement of "one first consultation per patient" (§3). Partial unique
        # index → race-proof, and only completed encounters count (a cancelled one
        # never blocks a genuine primera_vez).
        Index(
            "uq_encuentro_primera_vez",
            "tenant_id",
            "paciente_id",
            unique=True,
            postgresql_where=text("tipo = 'primera_vez' AND estado = 'completado'"),
        ),
        Index(
            "ix_encuentros_clinicos_paciente_estado",
            "tenant_id",
            "paciente_id",
            "estado",
        ),
        Index("ix_encuentros_clinicos_fecha_inicio", "fecha_inicio"),
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
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=False
    )
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedientes.id"), nullable=False
    )
    # A cita is optional: walk-ins and urgencias have no scheduled slot.
    cita_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("citas.id")
    )
    medico_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medicos.id"), nullable=False
    )
    # The credential used to sign; unknown until the encounter's note is signed.
    credencial_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medico_credenciales.id")
    )

    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default="subsecuente")
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="programado")
    # How ``tipo`` was decided; a manual override records who/when/why.
    clasificacion_origen: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="automatica"
    )
    motivo_correccion: Mapped[str | None] = mapped_column(Text)

    # The initial note this encounter produced. Set only on note creation; the link
    # never travels the other way onto a signed nota (§1.1). ``use_alter`` breaks the
    # notas ⇄ encuentros_clinicos FK cycle so create_all (test mode) can order them.
    nota_inicial_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notas.id", use_alter=True, name="fk_encuentro_nota_inicial"),
    )

    fecha_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_fin: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
