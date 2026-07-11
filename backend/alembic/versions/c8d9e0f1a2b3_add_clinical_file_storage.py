"""add tenant-scoped clinical file storage

Revision ID: c8d9e0f1a2b3
Revises: f9b8c7d6e5a4
Create Date: 2026-07-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: Union[str, None] = "f9b8c7d6e5a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_storage_usage",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("used_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("reserved_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("quota_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("used_bytes >= 0", name="ck_storage_used_nonnegative"),
        sa.CheckConstraint("reserved_bytes >= 0", name="ck_storage_reserved_nonnegative"),
        sa.CheckConstraint("quota_bytes >= 0", name="ck_storage_quota_nonnegative"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_table(
        "clinical_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paciente_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expediente_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("s3_key", sa.String(length=500), nullable=False),
        sa.Column("s3_version_id", sa.String(length=200), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=40), server_default="other", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending_upload", nullable=False),
        sa.Column("scan_status", sa.String(length=40), server_default="pending", nullable=False),
        sa.Column("uploaded_by", sa.String(length=200), nullable=False),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("size_bytes > 0", name="ck_clinical_file_size_positive"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("s3_key"),
    )
    op.create_index("ix_clinical_files_tenant_id", "clinical_files", ["tenant_id"])
    op.create_index("ix_clinical_files_paciente_id", "clinical_files", ["paciente_id"])
    op.create_index("ix_clinical_files_expediente_id", "clinical_files", ["expediente_id"])
    op.create_index("ix_clinical_files_status", "clinical_files", ["status"])

    op.execute(
        """
        INSERT INTO tenant_storage_usage (tenant_id)
        SELECT id FROM tenants
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )
    for table in ("tenant_storage_usage", "clinical_files"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO medrecord_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy_{table} ON {table}
            FOR ALL TO medrecord_app
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in ("clinical_files", "tenant_storage_usage"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM medrecord_app")
    op.drop_index("ix_clinical_files_status", table_name="clinical_files")
    op.drop_index("ix_clinical_files_expediente_id", table_name="clinical_files")
    op.drop_index("ix_clinical_files_paciente_id", table_name="clinical_files")
    op.drop_index("ix_clinical_files_tenant_id", table_name="clinical_files")
    op.drop_table("clinical_files")
    op.drop_table("tenant_storage_usage")
