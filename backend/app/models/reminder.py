import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.paciente import Paciente
    from app.models.tenant import Tenant

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Reminder(Base):
    """In-app appointment/task reminder. Not a clinical record — hard delete allowed."""

    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'dismissed')", name="reminders_status_check"
        ),
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
    paciente_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", foreign_keys=[tenant_id])
    paciente: Mapped["Paciente | None"] = relationship(
        "Paciente", foreign_keys=[paciente_id]
    )
