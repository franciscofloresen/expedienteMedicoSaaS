"""fase13a preferencias de interfaz (tema por usuario)

Revision ID: a7c9e1b3d5f7
Revises: f5b7d9e1a3c5
Create Date: 2026-08-18

Fase 13A (§5.5): per-identity visual theme preference. Keyed by
``(tenant_id, identity_provider_id)`` so a future Fase 14 membership can consume
it without renaming themes or sharing preferences between users of a tenant.

Stores only a theme KEY (validated against an allowlist in the API) — never a
color. Non-clinical, additive: if the frontend is rolled back the row stays inert
and the app uses the current default. Tenant-scoped, RLS FORCE + policy; editable.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c9e1b3d5f7"
down_revision: Union[str, None] = "f5b7d9e1a3c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PREF = "preferencias_interfaz_usuario"


def upgrade() -> None:
    op.create_table(
        _PREF,
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("identity_provider_id", sa.String(255), nullable=False),
        sa.Column("tema", sa.String(50), nullable=False, server_default="clinical-teal-dark"),
        sa.Column(
            "creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "modificado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "identity_provider_id", name="uq_preferencias_interfaz_identidad"
        ),
    )

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {_PREF} TO medrecord_app")
    op.execute(f"ALTER TABLE {_PREF} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_PREF} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_PREF} ON {_PREF}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_PREF} ON {_PREF}")
    op.execute(f"ALTER TABLE {_PREF} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {_PREF} FROM medrecord_app")
    op.drop_table(_PREF)
