"""beta_legal_docs_consent_whatsapp

Revision ID: f9b8c7d6e5a4
Revises: a7f1c2e9b4d0
Create Date: 2026-07-08 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f9b8c7d6e5a4"
down_revision: Union[str, None] = "a7f1c2e9b4d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("public_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_verification_tokens_tenant_id", "verification_tokens", ["tenant_id"])
    op.create_index("ix_verification_tokens_resource_type", "verification_tokens", ["resource_type"])
    op.create_index("ix_verification_tokens_resource_id", "verification_tokens", ["resource_id"])
    op.create_index("ix_verification_tokens_token", "verification_tokens", ["token"])

    op.add_column("notas", sa.Column("verification_token_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_notas_verification_token_id", "notas", "verification_tokens", ["verification_token_id"], ["id"])

    op.add_column("recetas", sa.Column("firmada_en", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recetas", sa.Column("firma_digital", postgresql.BYTEA(), nullable=True))
    op.add_column("recetas", sa.Column("firma_hash_contenido", sa.String(length=64), nullable=True))
    op.add_column("recetas", sa.Column("firma_kms_key_id", sa.String(length=200), nullable=True))
    op.add_column("recetas", sa.Column("firma_algoritmo", sa.String(length=30), server_default="ECDSA_SHA_256", nullable=True))
    op.add_column("recetas", sa.Column("es_editable", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("recetas", sa.Column("verification_token_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("recetas", sa.Column("medico_nombre", sa.String(length=200), nullable=True))
    op.add_column("recetas", sa.Column("medico_cedula", sa.String(length=20), nullable=True))
    op.add_column("recetas", sa.Column("medico_especialidad", sa.String(length=100), nullable=True))
    op.create_foreign_key("fk_recetas_verification_token_id", "recetas", "verification_tokens", ["verification_token_id"], ["id"])

    op.create_table(
        "consentimientos",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paciente_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expediente_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=20), server_default="1.0", nullable=False),
        sa.Column("procedimiento", sa.String(length=200), nullable=False),
        sa.Column("riesgos_principales", sa.Text(), nullable=True),
        sa.Column("contenido_renderizado", sa.Text(), nullable=False),
        sa.Column("firma_paciente_base64", sa.Text(), nullable=True),
        sa.Column("firmado_paciente_nombre", sa.String(length=200), nullable=True),
        sa.Column("firmado_paciente_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("firmado_medico_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hash_contenido", sa.String(length=64), nullable=True),
        sa.Column("firma_digital", postgresql.BYTEA(), nullable=True),
        sa.Column("verification_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("medico_nombre", sa.String(length=200), nullable=True),
        sa.Column("medico_cedula", sa.String(length=20), nullable=True),
        sa.Column("medico_especialidad", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
        sa.ForeignKeyConstraint(["expediente_id"], ["expedientes.id"]),
        sa.ForeignKeyConstraint(["verification_token_id"], ["verification_tokens.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consentimientos_tenant_id", "consentimientos", ["tenant_id"])
    op.create_index("ix_consentimientos_paciente_id", "consentimientos", ["paciente_id"])
    op.create_index("ix_consentimientos_expediente_id", "consentimientos", ["expediente_id"])

    op.create_table(
        "message_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paciente_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cita_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resource_type", sa.String(length=30), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("canal", sa.String(length=30), server_default="whatsapp_manual", nullable=False),
        sa.Column("template_key", sa.String(length=80), nullable=False),
        sa.Column("message_preview", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
        sa.ForeignKeyConstraint(["cita_id"], ["citas.id"]),
        sa.ForeignKeyConstraint(["sent_by"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_logs_tenant_id", "message_logs", ["tenant_id"])
    op.create_index("ix_message_logs_paciente_id", "message_logs", ["paciente_id"])

    for table in ("verification_tokens", "consentimientos", "message_logs"):
        op.execute(f"GRANT ALL ON TABLE {table} TO medrecord_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy_{table} ON {table}
            FOR ALL
            USING (tenant_id = current_setting('app.current_tenant')::uuid)
            """
        )
    op.execute(
        """
        CREATE POLICY public_verification_token_lookup ON verification_tokens
        FOR SELECT
        USING (true)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS public_verification_token_lookup ON verification_tokens")
    for table in ("message_logs", "consentimientos", "verification_tokens"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM medrecord_app")

    op.drop_index("ix_message_logs_paciente_id", table_name="message_logs")
    op.drop_index("ix_message_logs_tenant_id", table_name="message_logs")
    op.drop_table("message_logs")
    op.drop_index("ix_consentimientos_expediente_id", table_name="consentimientos")
    op.drop_index("ix_consentimientos_paciente_id", table_name="consentimientos")
    op.drop_index("ix_consentimientos_tenant_id", table_name="consentimientos")
    op.drop_table("consentimientos")

    op.drop_constraint("fk_recetas_verification_token_id", "recetas", type_="foreignkey")
    for column in (
        "medico_especialidad",
        "medico_cedula",
        "medico_nombre",
        "verification_token_id",
        "es_editable",
        "firma_algoritmo",
        "firma_kms_key_id",
        "firma_hash_contenido",
        "firma_digital",
        "firmada_en",
    ):
        op.drop_column("recetas", column)

    op.drop_constraint("fk_notas_verification_token_id", "notas", type_="foreignkey")
    op.drop_column("notas", "verification_token_id")

    op.drop_index("ix_verification_tokens_token", table_name="verification_tokens")
    op.drop_index("ix_verification_tokens_resource_id", table_name="verification_tokens")
    op.drop_index("ix_verification_tokens_resource_type", table_name="verification_tokens")
    op.drop_index("ix_verification_tokens_tenant_id", table_name="verification_tokens")
    op.drop_table("verification_tokens")
