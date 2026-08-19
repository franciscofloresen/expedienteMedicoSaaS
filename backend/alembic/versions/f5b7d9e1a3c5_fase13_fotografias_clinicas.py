"""fase13 fotografias clinicas (metadata sidecar)

Revision ID: f5b7d9e1a3c5
Revises: e3a5c7f9d1b3
Create Date: 2026-08-18

Fase 13 (§ "Fotografías clínicas con consentimiento específico, categoría,
lateralidad/zona anatómica, fecha y comparación; sin biometría/reconocimiento
automático"): a metadata sidecar over an existing ``clinical_files`` object.

The image bytes reuse the proven clinical-file S3 pipeline (SigV4/SSE-KMS,
malware scan). This table adds only clinical metadata + an optional link to the
specific consent, and a free-text ``grupo_comparacion`` to pair before/after
photos. No biometrics, no automatic recognition — descriptive metadata only.

Tenant-scoped, RLS FORCE + policy. The image itself (clinical_files) is the
delete-protected evidence; this descriptive sidecar stays editable.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5b7d9e1a3c5"
down_revision: Union[str, None] = "e3a5c7f9d1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FOTO = "fotografias_clinicas"


def upgrade() -> None:
    op.create_table(
        _FOTO,
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("paciente_id", UUID(as_uuid=True), sa.ForeignKey("pacientes.id"), nullable=False),
        sa.Column(
            "clinical_file_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clinical_files.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "consentimiento_id",
            UUID(as_uuid=True),
            sa.ForeignKey("consentimientos.id"),
            nullable=True,
        ),
        sa.Column("categoria", sa.String(30), nullable=False, server_default="general"),
        sa.Column("lateralidad", sa.String(15)),
        sa.Column("zona_anatomica", sa.String(120)),
        sa.Column("fecha_toma", sa.Date),
        sa.Column("grupo_comparacion", sa.String(80)),
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
            "categoria IN ('antes', 'despues', 'seguimiento', 'general')",
            name="fotografias_clinicas_categoria_check",
        ),
        sa.CheckConstraint(
            "lateralidad IS NULL OR lateralidad IN ('izquierda', 'derecha', 'bilateral', 'na')",
            name="fotografias_clinicas_lateralidad_check",
        ),
    )
    op.create_index("ix_fotografias_clinicas_tenant_pac", _FOTO, ["tenant_id", "paciente_id"])

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {_FOTO} TO medrecord_app")
    op.execute(f"ALTER TABLE {_FOTO} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_FOTO} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_FOTO} ON {_FOTO}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_FOTO} ON {_FOTO}")
    op.execute(f"ALTER TABLE {_FOTO} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {_FOTO} FROM medrecord_app")
    op.drop_index("ix_fotografias_clinicas_tenant_pac", table_name=_FOTO)
    op.drop_table(_FOTO)
