import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MessageLog(Base):
    __tablename__ = "message_logs"

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
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=False, index=True
    )
    cita_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("citas.id"))
    resource_type: Mapped[str | None] = mapped_column(String(30))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    canal: Mapped[str] = mapped_column(String(30), nullable=False, server_default="whatsapp_manual")
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    message_preview: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    sent_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
