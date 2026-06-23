import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """
    Request-level and entity-level audit log — NOM-004 + NOM-024 compliance.

    Two types of audit entries coexist:
    - Request-level: created by AuditMiddleware for every API request.
      Has method, path, status_code, duration_ms. May not have tabla/registro_id.
    - Entity-level: created by route handlers for specific data operations.
      Has tabla, registro_id, accion, datos_antes/datos_despues.

    This table is append-only. A database trigger prevents UPDATE and DELETE
    by the application role.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Request-level fields (from middleware)
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(500))
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)

    # Entity-level fields (from route handlers)
    tabla: Mapped[str | None] = mapped_column(String(50))
    registro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    accion: Mapped[str | None] = mapped_column(String(10))

    # Common fields
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    usuario_id: Mapped[str | None] = mapped_column(String(100), index=True)

    ip_origen: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )

    # Entity-level change tracking
    datos_antes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    datos_despues: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    exito: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    error_detalle: Mapped[str | None] = mapped_column(Text)
