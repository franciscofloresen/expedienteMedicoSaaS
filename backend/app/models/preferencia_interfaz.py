import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PreferenciaInterfazUsuario(Base):
    """Per-identity UI theme preference (Fase 13A §5.5).

    Keyed by (tenant_id, identity_provider_id). Stores only a theme KEY validated
    against an allowlist in the API — never a color. Editable, non-clinical.
    Tenant-scoped; RLS FORCE + policy live in the migration.
    """

    __tablename__ = "preferencias_interfaz_usuario"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "identity_provider_id", name="uq_preferencias_interfaz_identidad"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    identity_provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tema: Mapped[str] = mapped_column(String(50), nullable=False, server_default="clinical-teal-dark")

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    modificado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
