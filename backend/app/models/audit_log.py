import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Immutable, append-only NOM-004/NOM-024 audit trail (bitácora).

    The table, its immutability trigger (blocks UPDATE/DELETE), append-only
    grants, and RLS (audit_read_own / audit_write_all) are created by migrations
    — this model only maps the existing columns for the writer/reader.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Entity-level (nullable for request-level entries)
    tabla: Mapped[str | None] = mapped_column(String(50))
    registro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    accion: Mapped[str | None] = mapped_column(String(10))

    # Actor / tenant
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    identity_provider_id: Mapped[str | None] = mapped_column(String(128))
    session_id: Mapped[str | None] = mapped_column(String(128))
    factor_verification_age: Mapped[list[int] | None] = mapped_column(JSONB)
    ip_origen: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    # Optional change payloads
    datos_antes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    datos_despues: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    exito: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    error_detalle: Mapped[str | None] = mapped_column(Text)

    # Request-level
    request_id: Mapped[str | None] = mapped_column(String(36))
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(500))
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
