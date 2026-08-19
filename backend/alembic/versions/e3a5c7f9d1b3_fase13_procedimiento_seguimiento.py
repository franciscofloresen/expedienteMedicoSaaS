"""fase13 checklists de procedimiento y eventos adversos

Revision ID: e3a5c7f9d1b3
Revises: d1f3a5c7e9b1
Create Date: 2026-08-18

Fase 13 (§ "Checklist pre/post procedimiento y seguimiento de eventos adversos"):
two tenant-scoped tables for dermatology/aesthetics procedures.

* ``procedimiento_checklists`` — a pre- or post-procedure checklist (items JSONB).
* ``eventos_adversos`` — adverse-event tracking with severity and open/resolved state.

Both are working clinical-workflow records the doctor edits over time (not signed
snapshots), so they KEEP DELETE/UPDATE — no immutability trigger. Each carries its
own ``tenant_id`` with RLS ``FORCE`` + a tenant_isolation policy. Schema-only.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3a5c7f9d1b3"
down_revision: Union[str, None] = "d1f3a5c7e9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHK = "procedimiento_checklists"
_AE = "eventos_adversos"


def _rls(table: str) -> None:
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO medrecord_app")
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def upgrade() -> None:
    op.create_table(
        _CHK,
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("paciente_id", UUID(as_uuid=True), sa.ForeignKey("pacientes.id"), nullable=False),
        sa.Column(
            "encuentro_id",
            UUID(as_uuid=True),
            sa.ForeignKey("encuentros_clinicos.id"),
            nullable=True,
        ),
        sa.Column("momento", sa.String(10), nullable=False),
        sa.Column("items", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("observaciones", sa.Text),
        sa.Column("creado_por", UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "modificado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("momento IN ('pre', 'post')", name="procedimiento_checklists_momento_check"),
    )
    op.create_index("ix_procedimiento_checklists_tenant_pac", _CHK, ["tenant_id", "paciente_id"])
    _rls(_CHK)

    op.create_table(
        _AE,
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("paciente_id", UUID(as_uuid=True), sa.ForeignKey("pacientes.id"), nullable=False),
        sa.Column(
            "encuentro_id",
            UUID(as_uuid=True),
            sa.ForeignKey("encuentros_clinicos.id"),
            nullable=True,
        ),
        sa.Column("descripcion", sa.Text, nullable=False),
        sa.Column("severidad", sa.String(10), nullable=False, server_default="leve"),
        sa.Column("fecha", sa.Date),
        sa.Column("manejo", sa.Text),
        sa.Column("estado", sa.String(10), nullable=False, server_default="abierto"),
        sa.Column("creado_por", UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "modificado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "severidad IN ('leve', 'moderado', 'grave')", name="eventos_adversos_severidad_check"
        ),
        sa.CheckConstraint("estado IN ('abierto', 'resuelto')", name="eventos_adversos_estado_check"),
    )
    op.create_index("ix_eventos_adversos_tenant_pac", _AE, ["tenant_id", "paciente_id"])
    _rls(_AE)


def downgrade() -> None:
    for table in (_AE, _CHK):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM medrecord_app")
    op.drop_index("ix_eventos_adversos_tenant_pac", table_name=_AE)
    op.drop_table(_AE)
    op.drop_index("ix_procedimiento_checklists_tenant_pac", table_name=_CHK)
    op.drop_table(_CHK)
