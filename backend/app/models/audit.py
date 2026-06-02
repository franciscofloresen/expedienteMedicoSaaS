import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "accion IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')",
            name="audit_log_accion_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tabla: Mapped[str] = mapped_column(String(50), nullable=False)
    registro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    accion: Mapped[str] = mapped_column(String(10), nullable=False)
    
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    
    ip_origen: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
    
    datos_antes: Mapped[dict | None] = mapped_column(JSONB)
    datos_despues: Mapped[dict | None] = mapped_column(JSONB)
    
    exito: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    error_detalle: Mapped[str | None] = mapped_column(Text)
