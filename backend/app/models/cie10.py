from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CIE10(Base):
    """Shared CIE-10 reference catalog (Mexican DGIS/SSA version).

    Fase 3 (roadmap §5.3): extended in place — PK stays ``code`` (dotted form,
    e.g. ``J06.9``). This is **shared reference data**, so it carries no ``tenant_id``
    and no RLS (§1.2). ``normalized_description`` (lowercase, accent-stripped in Python)
    backs the GIN trigram search; ``unaccent()`` is deliberately NOT used in the index
    expression because it is not immutable (§3). Rows are loaded by the idempotent admin
    importer after deploy, never inside Alembic (§1.5).
    """

    __tablename__ = "cie10"

    # Not using UUID, PK is the standard dotted code (e.g. J06.9)
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(100), index=True)

    # Fase 3 extensions (all nullable / defaulted — populated by the importer).
    normalized_description: Mapped[str | None] = mapped_column(Text)
    chapter_code: Mapped[str | None] = mapped_column(String(10))
    chapter_description: Mapped[str | None] = mapped_column(String(300))
    group_code: Mapped[str | None] = mapped_column(String(20))
    category_code: Mapped[str | None] = mapped_column(String(20), index=True)
    parent_code: Mapped[str | None] = mapped_column(String(20))
    # Whether a clinician may pick this code as a diagnosis, and whether it is currently
    # valid in the catalog. The importer sets both from the catalog's VALID flag.
    selectable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    catalog_version: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(100))
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    actualizado_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
