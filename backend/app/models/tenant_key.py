import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import Tenant

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TenantKey(Base):
    """Stores the KMS-encrypted Data Encryption Key (DEK) for envelope encryption."""

    __tablename__ = "tenant_keys"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    encrypted_dek: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    kms_key_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="tenant_key")
