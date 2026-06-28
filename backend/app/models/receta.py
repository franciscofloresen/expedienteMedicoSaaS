import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.nota import Nota

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Receta(Base):
    __tablename__ = "recetas"

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
        UUID(as_uuid=True), ForeignKey("notas.id"), nullable=False, index=True
    )

    # Ponytail rule: JSONB evita tabla PrescriptionMedication y simplifica el backend
    medicamentos: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    indicaciones_generales: Mapped[str | None] = mapped_column(Text)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    nota: Mapped["Nota"] = relationship("Nota")
