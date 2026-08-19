"""fase13 plantillas de nota configurables

Revision ID: d1f3a5c7e9b1
Revises: c7e9f1a3b5d7
Create Date: 2026-08-18

Fase 13 (§ "Plantillas configurables de historia, evolución, exploración y
procedimiento"): a doctor-authored note template is a versioned JSON of field
pre-fills (``campos``) that seeds the note editor — NOT a generic form builder
(roadmap: "personalización limitada por configuración JSON versionada").

Editable preference, not clinical evidence: like favoritos it KEEPS DELETE/UPDATE
(no REVOKE DELETE, no immutability trigger). Tenant-scoped with its own
``tenant_id`` + RLS ``FORCE`` + ``tenant_isolation_nota_plantillas`` policy.
``version`` bumps on edit so a template change is traceable. Schema-only, no backfill.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f3a5c7e9b1"
down_revision: Union[str, None] = "c7e9f1a3b5d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TPL = "nota_plantillas"


def upgrade() -> None:
    op.create_table(
        _TPL,
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("campos", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("creado_por", UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "modificado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_nota_plantillas_tenant", _TPL, ["tenant_id"])

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {_TPL} TO medrecord_app")
    op.execute(f"ALTER TABLE {_TPL} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TPL} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_TPL} ON {_TPL}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_TPL} ON {_TPL}")
    op.execute(f"ALTER TABLE {_TPL} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {_TPL} FROM medrecord_app")
    op.drop_index("ix_nota_plantillas_tenant", table_name=_TPL)
    op.drop_table(_TPL)
