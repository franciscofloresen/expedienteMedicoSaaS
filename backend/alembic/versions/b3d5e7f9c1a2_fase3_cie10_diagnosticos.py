"""fase3 cie10 completo y diagnosticos estructurados

Revision ID: b3d5e7f9c1a2
Revises: a2f4c6e8b0d1
Create Date: 2026-07-15

Fase 3 del ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2 (§5.3/§6 Fase 3): trae el catálogo
CIE-10 real (versión mexicana DGIS/SSA) con búsqueda sin acentos, y **diagnósticos
estructurados múltiples por nota** (``nota_diagnosticos``), reemplazando el texto libre
``notas.diagnostico_cie10`` (que se conserva como evidencia legada).

Migración **solo esquema** (§1.5): extiende ``cie10`` (dato de referencia compartido,
sin RLS — §1.2) con columnas nullable/defaulted (metadata-only → no toca filas), crea
la tabla tenant-scoped ``nota_diagnosticos`` y la extensión ``pg_trgm`` (cero infra,
disponible en RDS PG15). Sin backfill sobre notas firmadas.

Regla de oro respetada (§1.1): **cero UPDATE a notas firmadas**. ``nota_diagnosticos``
apunta *hacia* la nota (``nota_id``); la nota nunca se modifica. La extracción de
diagnósticos legados (payload admin) crea filas aquí sin tocar la nota.

Búsqueda sin acentos (§3): índice GIN trigram sobre ``normalized_description``. La
normalización se hace en **Python** (importador + endpoint), NO con ``unaccent()`` en la
expresión del índice (no es immutable).

Tenant-scoped (§1.2): ``nota_diagnosticos`` lleva su propia ``tenant_id``, RLS
``ENABLE`` + ``FORCE`` + política ``tenant_isolation_nota_diagnosticos`` y
``REVOKE DELETE`` + trigger ``prevent_nota_diagnosticos_deletion`` (reusa la función
compartida ``prevent_clinical_deletion``): un diagnóstico es evidencia clínica, no se
borra. Un solo diagnóstico principal por nota lo garantiza el índice único parcial
``uq_nota_diagnostico_principal`` (§5.3).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d5e7f9c1a2"
down_revision: Union[str, None] = "a2f4c6e8b0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIAG = "nota_diagnosticos"

# New columns added to the shared reference table ``cie10``. Names listed here for the
# downgrade; the Column objects are built fresh in upgrade() (a Column instance can only
# belong to one table, so we never reuse them). All nullable / defaulted → metadata-only
# ADD COLUMN, so the existing rows are never rewritten.
_CIE10_COLUMN_NAMES = (
    "normalized_description",
    "chapter_code",
    "chapter_description",
    "group_code",
    "category_code",
    "parent_code",
    "selectable",
    "active",
    "catalog_version",
    "source",
    "creado_en",
    "actualizado_en",
)


def upgrade() -> None:
    # ── 1. Extensión pg_trgm (cero infra; requiere rol master/superusuario) ──
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── 2. Extender cie10 (referencia compartida, sin RLS — §1.2) ──
    op.add_column("cie10", sa.Column("normalized_description", sa.Text))
    op.add_column("cie10", sa.Column("chapter_code", sa.String(10)))
    op.add_column("cie10", sa.Column("chapter_description", sa.String(300)))
    op.add_column("cie10", sa.Column("group_code", sa.String(20)))
    op.add_column("cie10", sa.Column("category_code", sa.String(20)))
    op.add_column("cie10", sa.Column("parent_code", sa.String(20)))
    op.add_column(
        "cie10",
        sa.Column("selectable", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "cie10",
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.add_column("cie10", sa.Column("catalog_version", sa.String(50)))
    op.add_column("cie10", sa.Column("source", sa.String(100)))
    op.add_column(
        "cie10",
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.add_column(
        "cie10",
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # Índice GIN trigram para búsqueda sin acentos sobre la descripción normalizada
    # (poblada por el importador en Python; nada de unaccent() en el índice — §3).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cie10_norm_desc_trgm "
        "ON cie10 USING gin (normalized_description gin_trgm_ops)"
    )
    op.create_index("ix_cie10_category_code", "cie10", ["category_code"])

    # ── 3. Tabla nota_diagnosticos (tenant-scoped, §1.2) ──
    op.create_table(
        _DIAG,
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "nota_id",
            UUID(as_uuid=True),
            sa.ForeignKey("notas.id", name="fk_nota_diagnostico_nota"),
            nullable=False,
        ),
        sa.Column(
            "cie10_code",
            sa.String(20),
            sa.ForeignKey("cie10.code", name="fk_nota_diagnostico_cie10"),
            nullable=False,
        ),
        sa.Column("orden", sa.Integer, nullable=False, server_default="0"),
        sa.Column("es_principal", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("certeza", sa.String(20), nullable=False, server_default="presuntivo"),
        # Snapshot of the catalog description/version at the moment the diagnosis was
        # recorded, so a later catalog revision never rewrites clinical history.
        sa.Column("descripcion_snapshot", sa.String(500)),
        sa.Column("version_snapshot", sa.String(50)),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("creado_por", UUID(as_uuid=True), sa.ForeignKey("tenants.id")),
        sa.CheckConstraint(
            "certeza IN ('confirmado', 'presuntivo', 'descartado')",
            name="nota_diagnosticos_certeza_check",
        ),
    )
    op.create_index("ix_nota_diagnosticos_tenant_id", _DIAG, ["tenant_id"])
    op.create_index("ix_nota_diagnosticos_nota", _DIAG, ["tenant_id", "nota_id"])
    op.create_index("ix_nota_diagnosticos_cie10_code", _DIAG, ["cie10_code"])
    # Un solo diagnóstico principal por nota (§5.3): índice único parcial, a prueba de
    # carreras (mismo patrón que uq_encuentro_primera_vez de la Fase 2).
    op.create_index(
        "uq_nota_diagnostico_principal",
        _DIAG,
        ["nota_id"],
        unique=True,
        postgresql_where=sa.text("es_principal"),
    )

    # ── 4. RLS + política + grants ──
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE {_DIAG} TO medrecord_app")
    op.execute(f"ALTER TABLE {_DIAG} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_DIAG} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_DIAG} ON {_DIAG}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
        """
    )

    # ── 5. Protección de borrado: rol + trigger (§5.3) ──
    # Un diagnóstico es evidencia clínica: se corrige con una versión/estado, no se borra.
    op.execute(f"REVOKE DELETE ON {_DIAG} FROM medrecord_app")
    op.execute(f"DROP TRIGGER IF EXISTS prevent_{_DIAG}_deletion ON {_DIAG}")
    op.execute(
        f"""
        CREATE TRIGGER prevent_{_DIAG}_deletion
        BEFORE DELETE ON {_DIAG}
        FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion()
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS prevent_{_DIAG}_deletion ON {_DIAG}")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_DIAG} ON {_DIAG}")
    op.execute(f"ALTER TABLE {_DIAG} DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON TABLE {_DIAG} FROM medrecord_app")
    op.drop_table(_DIAG)

    op.drop_index("ix_cie10_category_code", table_name="cie10")
    op.execute("DROP INDEX IF EXISTS ix_cie10_norm_desc_trgm")
    for name in reversed(_CIE10_COLUMN_NAMES):
        op.drop_column("cie10", name)

    # Nothing else uses pg_trgm today; drop it so the round-trip is clean.
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
