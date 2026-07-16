"""fase5 firmantes, documento final y revocacion

Revision ID: e5f7a9c1d3b5
Revises: d4e5f6a7b8c9
Create Date: 2026-07-16

Schema-only and production-safe: no historical consent is updated. New evidence lives
in tenant-scoped lateral tables. A consent becomes immutable after the doctor signature;
the sole compatibility exception is attaching a previously missing verification token
without changing any other signed field.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5f7a9c1d3b5"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EVIDENCE_TABLES = (
    "consentimiento_firmantes",
    "consentimiento_documentos_finales",
    "consentimiento_revocaciones",
)


def _secure_evidence_table(table: str) -> None:
    op.execute(f"REVOKE ALL ON TABLE {table} FROM medrecord_app")
    op.execute(f"GRANT SELECT, INSERT ON TABLE {table} TO medrecord_app")
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{table} ON {table}
        FOR ALL TO medrecord_app
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER prevent_{table}_deletion
        BEFORE DELETE ON {table}
        FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion()
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {table}_immutable
        BEFORE UPDATE ON {table}
        FOR EACH ROW EXECUTE FUNCTION prevent_consent_evidence_modification()
        """
    )


def upgrade() -> None:
    op.add_column(
        "consentimientos", sa.Column("firma_kms_key_id", sa.String(200), nullable=True)
    )
    op.add_column(
        "consentimientos", sa.Column("firma_algoritmo", sa.String(30), nullable=True)
    )
    op.add_column(
        "consentimientos",
        sa.Column("medico_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "consentimientos",
        sa.Column("credencial_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_consentimientos_medico", "consentimientos", "medicos", ["medico_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_consentimientos_credencial",
        "consentimientos",
        "medico_credenciales",
        ["credencial_id"],
        ["id"],
    )
    op.create_index("ix_consentimientos_medico_id", "consentimientos", ["medico_id"])
    op.create_index("ix_consentimientos_credencial_id", "consentimientos", ["credencial_id"])

    op.create_table(
        "consentimiento_firmantes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "consentimiento_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consentimientos.id"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("relacion_paciente", sa.String(120), nullable=True),
        sa.Column("motivo_representacion", sa.Text(), nullable=True),
        sa.Column("firma_base64", sa.Text(), nullable=False),
        sa.Column("firma_sha256", sa.String(64), nullable=False),
        sa.Column(
            "firmado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "tipo IN ('paciente', 'representante', 'tutor', 'testigo')",
            name="consentimiento_firmante_tipo_check",
        ),
        sa.CheckConstraint("orden BETWEEN 0 AND 2", name="consentimiento_firmante_orden_check"),
        sa.UniqueConstraint(
            "consentimiento_id",
            "tipo",
            "orden",
            name="uq_consentimiento_firmante_tipo_orden",
        ),
    )
    op.create_index(
        "ix_consentimiento_firmantes_tenant_id", "consentimiento_firmantes", ["tenant_id"]
    )
    op.create_index(
        "ix_consentimiento_firmantes_consentimiento_id",
        "consentimiento_firmantes",
        ["consentimiento_id"],
    )

    op.create_table(
        "consentimiento_documentos_finales",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "consentimiento_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consentimientos.id"),
            nullable=False,
        ),
        sa.Column("s3_bucket", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("s3_version_id", sa.String(200), nullable=True),
        sa.Column("s3_etag", sa.String(100), nullable=True),
        sa.Column("contenido_sha256", sa.String(64), nullable=False),
        sa.Column(
            "content_type", sa.String(100), nullable=False, server_default="application/pdf"
        ),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint("size_bytes > 0", name="consentimiento_documento_size_check"),
        sa.UniqueConstraint("consentimiento_id", name="uq_consentimiento_documento_final"),
        sa.UniqueConstraint("s3_key", name="uq_consentimiento_documento_s3_key"),
    )
    op.create_index(
        "ix_consentimiento_documentos_finales_tenant_id",
        "consentimiento_documentos_finales",
        ["tenant_id"],
    )
    op.create_index(
        "ix_consentimiento_documentos_finales_consentimiento_id",
        "consentimiento_documentos_finales",
        ["consentimiento_id"],
    )

    op.create_table(
        "consentimiento_revocaciones",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "consentimiento_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consentimientos.id"),
            nullable=False,
        ),
        sa.Column("motivo", sa.Text(), nullable=False),
        sa.Column("actor_nombre", sa.String(200), nullable=False),
        sa.Column("actor_tipo", sa.String(30), nullable=False, server_default="medico"),
        sa.Column(
            "revocado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "actor_tipo IN ('medico', 'administrador')",
            name="consentimiento_revocacion_actor_check",
        ),
        sa.UniqueConstraint("consentimiento_id", name="uq_consentimiento_revocacion"),
    )
    op.create_index(
        "ix_consentimiento_revocaciones_tenant_id",
        "consentimiento_revocaciones",
        ["tenant_id"],
    )
    op.create_index(
        "ix_consentimiento_revocaciones_consentimiento_id",
        "consentimiento_revocaciones",
        ["consentimiento_id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_consent_evidence_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Consent signature, final-document and revocation evidence is immutable';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )

    for table in _EVIDENCE_TABLES:
        _secure_evidence_table(table)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_signed_consent_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.firmado_medico_en IS NOT NULL THEN
                IF to_jsonb(NEW) = to_jsonb(OLD) THEN
                    RETURN NEW;
                END IF;
                IF OLD.verification_token_id IS NULL
                   AND NEW.verification_token_id IS NOT NULL
                   AND (to_jsonb(NEW) - 'verification_token_id') =
                       (to_jsonb(OLD) - 'verification_token_id')
                THEN
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'Signed consents are immutable; revoke with a related event';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER consentimientos_signed_immutable
        BEFORE UPDATE ON consentimientos
        FOR EACH ROW EXECUTE FUNCTION prevent_signed_consent_modification()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS consentimientos_signed_immutable ON consentimientos")
    op.execute("DROP FUNCTION IF EXISTS prevent_signed_consent_modification()")

    for table in reversed(_EVIDENCE_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS {table}_immutable ON {table}")
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_deletion ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.drop_table(table)
    op.execute("DROP FUNCTION IF EXISTS prevent_consent_evidence_modification()")

    op.drop_index("ix_consentimientos_credencial_id", table_name="consentimientos")
    op.drop_index("ix_consentimientos_medico_id", table_name="consentimientos")
    op.drop_constraint("fk_consentimientos_credencial", "consentimientos", type_="foreignkey")
    op.drop_constraint("fk_consentimientos_medico", "consentimientos", type_="foreignkey")
    op.drop_column("consentimientos", "credencial_id")
    op.drop_column("consentimientos", "medico_id")
    op.drop_column("consentimientos", "firma_algoritmo")
    op.drop_column("consentimientos", "firma_kms_key_id")
