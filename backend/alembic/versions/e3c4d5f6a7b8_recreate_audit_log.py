"""recreate audit_log table (immutable bitácora) for the audit feature

Revision ID: e3c4d5f6a7b8
Revises: d2b3c4e5f6a7
Create Date: 2026-07-07 00:30:00.000000

The audit_log table was dropped by 4f4145428368 ("remove dead tables"). The
audit feature now surfaces an immutable bitácora (NOM-024), so this recreates
the table in its final shape — request-level columns, RLS (read-own / write-all),
append-only grants, and the immutability trigger.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3c4d5f6a7b8"
down_revision: Union[str, None] = "d2b3c4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        # Entity-level (nullable for request-level entries)
        sa.Column("tabla", sa.String(length=50), nullable=True),
        sa.Column("registro_id", sa.UUID(), nullable=True),
        sa.Column("accion", sa.String(length=10), nullable=True),
        # Actor / tenant
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("usuario_id", sa.UUID(), nullable=True),
        sa.Column("ip_origen", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Optional change payloads
        sa.Column("datos_antes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "datos_despues", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "exito", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("error_detalle", sa.Text(), nullable=True),
        # Request-level
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audit_log_tenant_id"), "audit_log", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_timestamp"), "audit_log", ["timestamp"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_request_id"), "audit_log", ["request_id"], unique=False
    )

    # ── RLS: tenants read only their own rows; the system may insert for any tenant ──
    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_read_own ON audit_log
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant')::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY audit_write_all ON audit_log
            FOR INSERT
            WITH CHECK (true)
        """
    )

    # ── Append-only grants for the application role ──
    op.execute("GRANT SELECT, INSERT ON audit_log TO medrecord_app")
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO medrecord_app"
    )
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM medrecord_app")

    # ── Immutability trigger (blocks UPDATE/DELETE) ──
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit log records cannot be modified or deleted '
            '(NOM-004/NOM-024 compliance)';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_read_own ON audit_log")
    op.execute("DROP POLICY IF EXISTS audit_write_all ON audit_log")
    op.drop_index(op.f("ix_audit_log_request_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_timestamp"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_tenant_id"), table_name="audit_log")
    op.drop_table("audit_log")
