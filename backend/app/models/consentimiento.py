import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Consentimiento(Base):
    __tablename__ = "consentimientos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedientes.id"), nullable=False, index=True
    )
    
    tipo: Mapped[str | None] = mapped_column(String(50))
    s3_key: Mapped[str | None] = mapped_column(String(500))
    hash_documento: Mapped[str | None] = mapped_column(String(64))
    firmado_por: Mapped[str | None] = mapped_column(String(200))
    firmado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
