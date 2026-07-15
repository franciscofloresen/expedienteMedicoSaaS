"""fase1 medicos y credenciales

Revision ID: efb69dbb7dfb
Revises: 8d3d86bc8393
Create Date: 2026-07-14

Fase 1 del ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2 (§5.1/§6.1-6.2): introduce la
identidad profesional (``medicos``) y sus credenciales (``medico_credenciales``),
desacopladas del consultorio (``tenants``).

Ambas tablas son tenant-scoped: RLS ``ENABLE`` + ``FORCE`` + política
``tenant_isolation_<tabla>`` y ``REVOKE DELETE`` + trigger ``prevent_<tabla>_deletion``
(reusa la función compartida ``prevent_clinical_deletion``), igual que las demás
tablas clínicas (§1.2). ``medico_credenciales`` lleva su **propia** ``tenant_id``
porque RLS no puede seguir el FK a ``medicos`` (§1.2).

Índices únicos parciales (§5.1):
  * ``uq_credencial_numero_por_medico`` — número normalizado único por médico.
  * ``uq_credencial_predeterminada_por_medico`` — una sola credencial
    predeterminada **activa** por médico (a prueba de carreras).

Backfill: un ``medico`` + una credencial predeterminada por tenant, tomando
``nombre_medico``/``cedula``/``especialidad`` de ``tenants``. Toca **solo tablas
nuevas** → cero riesgo del trigger de inmutabilidad de notas (§1.1). El backfill
corre **antes** de ``FORCE ROW LEVEL SECURITY`` porque FORCE también aplica al
owner y ``app.current_tenant`` no está fijado durante la migración (mismo orden
que la migración de clinical files).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "efb69dbb7dfb"
down_revision: Union[str, None] = "8d3d86bc8393"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("medicos", "medico_credenciales")

# The normalized-number expression below —
#   upper(regexp_replace(coalesce(t.cedula, ''), '\s+', '', 'g'))
# — mirrors app.core.credenciales.normalize_credential_number. Keep them in lockstep.


def upgrade() -> None:
    # ── 1. Esquema (sin RLS todavía, para poder hacer el backfill como owner) ──
    op.create_table(
        "medicos",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("identity_provider_id", sa.String(100)),
        sa.Column("nombre_completo", sa.String(200), nullable=False),
        sa.Column("rfc", sa.String(13)),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_medicos_tenant_id", "medicos", ["tenant_id"])
    op.create_index("ix_medicos_identity_provider_id", "medicos", ["identity_provider_id"])

    op.create_table(
        "medico_credenciales",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "medico_id",
            UUID(as_uuid=True),
            sa.ForeignKey("medicos.id"),
            nullable=False,
        ),
        sa.Column("numero", sa.String(50), nullable=False),
        sa.Column("numero_normalizado", sa.String(50), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="general"),
        sa.Column("especialidad", sa.String(100)),
        sa.Column("institucion", sa.String(200)),
        sa.Column("autoridad_emisora", sa.String(200)),
        sa.Column("pais", sa.String(2), nullable=False, server_default="MX"),
        sa.Column("anio_expedicion", sa.Integer),
        sa.Column(
            "es_predeterminada", sa.Boolean, nullable=False, server_default=sa.text("false")
        ),
        sa.Column("activa", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("verificada", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("verificada_en", sa.DateTime(timezone=True)),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_medico_credenciales_tenant_id", "medico_credenciales", ["tenant_id"])
    op.create_index("ix_medico_credenciales_medico_id", "medico_credenciales", ["medico_id"])
    op.create_index(
        "uq_credencial_numero_por_medico",
        "medico_credenciales",
        ["medico_id", "numero_normalizado"],
        unique=True,
    )
    op.create_index(
        "uq_credencial_predeterminada_por_medico",
        "medico_credenciales",
        ["medico_id"],
        unique=True,
        postgresql_where=sa.text("es_predeterminada AND activa"),
    )

    # ── 2. Backfill (owner, sin RLS aún): un médico + credencial por tenant ──
    # Guardas NOT EXISTS → re-ejecutar la cadena sobre una BD que ya los tiene es
    # idempotente. Toca solo tablas nuevas (§1.1).
    op.execute(
        """
        INSERT INTO medicos (id, tenant_id, nombre_completo, activo)
        SELECT gen_random_uuid(), t.id, t.nombre_medico, true
        FROM tenants t
        WHERE NOT EXISTS (SELECT 1 FROM medicos m WHERE m.tenant_id = t.id)
        """
    )
    op.execute(
        """
        INSERT INTO medico_credenciales
            (id, tenant_id, medico_id, numero, numero_normalizado,
             tipo, especialidad, es_predeterminada, activa)
        SELECT gen_random_uuid(), t.id, m.id, t.cedula,
               upper(regexp_replace(coalesce(t.cedula, ''), '\\s+', '', 'g')),
               'general', t.especialidad, true, true
        FROM tenants t
        JOIN medicos m ON m.tenant_id = t.id
        WHERE t.cedula IS NOT NULL AND t.cedula <> ''
          AND NOT EXISTS (
              SELECT 1 FROM medico_credenciales c WHERE c.medico_id = m.id
          )
        """
    )

    # ── 3. RLS + política + grants (después del backfill) ──
    for table in _TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {table} TO medrecord_app")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
            """
        )

    # ── 4. Protección de borrado: rol + trigger (§5.1) ──
    # Una credencial usada en documentos firmados se desactiva, nunca se borra.
    for table in _TABLES:
        op.execute(f"REVOKE DELETE ON {table} FROM medrecord_app")
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_deletion ON {table}")
        op.execute(
            f"""
            CREATE TRIGGER prevent_{table}_deletion
            BEFORE DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion()
            """
        )


def downgrade() -> None:
    # Orden inverso; medico_credenciales primero por el FK a medicos.
    for table in reversed(_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_deletion ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM medrecord_app")
    op.drop_table("medico_credenciales")
    op.drop_table("medicos")
