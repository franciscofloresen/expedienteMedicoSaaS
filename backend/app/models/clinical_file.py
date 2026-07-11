import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TenantStorageUsage(Base):
    __tablename__ = "tenant_storage_usage"
    __table_args__ = (
        CheckConstraint("used_bytes >= 0", name="ck_storage_used_nonnegative"),
        CheckConstraint("reserved_bytes >= 0", name="ck_storage_reserved_nonnegative"),
        CheckConstraint("quota_bytes >= 0", name="ck_storage_quota_nonnegative"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), primary_key=True
    )
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    quota_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ClinicalFile(Base):
    __tablename__ = "clinical_files"
    __table_args__ = (CheckConstraint("size_bytes > 0", name="ck_clinical_file_size_positive"),)

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
    expediente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedientes.id"), nullable=False, index=True
    )
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    s3_version_id: Mapped[str | None] = mapped_column(String(200))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, server_default="other")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="pending_upload", index=True
    )
    scan_status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="pending")
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
