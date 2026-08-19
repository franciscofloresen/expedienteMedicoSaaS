"""fase13 favoritos del medico

Revision ID: c7e9f1a3b5d7
Revises: a9c1e3f5b7d9
Create Date: 2026-08-18

Fase 13 (§ "Favoritos del médico"): snippets reutilizables del médico —
diagnósticos, planes, indicaciones y recetas — para reducir el tiempo de
documentación. Siempre editables; **no** son evidencia clínica ni snapshot
firmado, así que a diferencia de las tablas clínicas (§1.1/§1.2) SÍ se pueden
editar y borrar: sin ``REVOKE DELETE`` ni trigger de inmutabilidad.

Tenant-scoped (§1.2): lleva su propia ``tenant_id`` con RLS ``ENABLE`` +
``FORCE`` + política ``tenant_isolation_medico_favoritos``. Migración solo
esquema, tabla nueva, sin backfill.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e9f1a3b5d7"
down_revision: Union[str, None] = "a9c1e3f5b7d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FAV = "medico_favoritos"


def upgrade() -> None:
    op.create_table(
        _FAV,
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("texto", sa.Text, nullable=False),
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
        sa.CheckConstraint(
            "kind IN ('diagnostico', 'plan', 'indicacion', 'receta')",
            name="medico_favoritos_kind_check",
        ),
    )
    op.create_index("ix_medico_favoritos_tenant_kind", _FAV, ["tenant_id", "kind"])

    # Least privilege: the app role reads/writes/edits/deletes its own favorites
    # (they are editable preferences, not immutable clinical evidence).
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {_FAV} TO medrecord_app")
    op.execute(f"ALTER TABLE {_FAV} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_FAV} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_FAV} ON {_FAV}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_FAV} ON {_FAV}")
    op.execute(f"ALTER TABLE {_FAV} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {_FAV} FROM medrecord_app")
    op.drop_index("ix_medico_favoritos_tenant_kind", table_name=_FAV)
    op.drop_table(_FAV)
