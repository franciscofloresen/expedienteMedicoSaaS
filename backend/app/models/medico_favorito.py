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


class MedicoFavorito(Base):
    """A reusable snippet saved by the doctor: diagnosis, plan, indication or
    prescription (Fase 13, "Favoritos del médico").

    Unlike clinical tables, favorites are **editable preferences**, not immutable
    evidence — so they keep DELETE/UPDATE and carry no immutability trigger. They
    are tenant-scoped with their own ``tenant_id`` (RLS cannot follow FKs — §1.2);
    the RLS ``FORCE`` + ``tenant_isolation_medico_favoritos`` policy lives in the
    migration.
    """

    __tablename__ = "medico_favoritos"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('diagnostico', 'plan', 'indicacion', 'receta')",
            name="medico_favoritos_kind_check",
        ),
        Index("ix_medico_favoritos_tenant_kind", "tenant_id", "kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    creado_por: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id")
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
