"""Fase 8: additive indexes for measured clinical read paths.

Revision ID: f6a8b0c2d4e6
Revises: e5f7a9c1d3b5
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f6a8b0c2d4e6"
down_revision: str | None = "e5f7a9c1d3b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Longitudinal reads filter by expediente and render newest first.
    op.create_index(
        "ix_notas_expediente_creado_id",
        "notas",
        ["expediente_id", "creado_en", "id"],
        unique=False,
    )
    op.create_index(
        "ix_consentimientos_expediente_creado_id",
        "consentimientos",
        ["expediente_id", "created_at", "id"],
        unique=False,
    )

    # Patient lookup uses contains-search on these three fields. pg_trgm already
    # exists from Fase 3 and lets PostgreSQL combine the branches with BitmapOr.
    op.create_index(
        "ix_pacientes_nombre_trgm",
        "pacientes",
        ["nombre_completo"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"nombre_completo": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_pacientes_curp_trgm",
        "pacientes",
        ["curp"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"curp": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_pacientes_telefono_trgm",
        "pacientes",
        ["telefono"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"telefono": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_pacientes_telefono_trgm", table_name="pacientes")
    op.drop_index("ix_pacientes_curp_trgm", table_name="pacientes")
    op.drop_index("ix_pacientes_nombre_trgm", table_name="pacientes")
    op.drop_index("ix_consentimientos_expediente_creado_id", table_name="consentimientos")
    op.drop_index("ix_notas_expediente_creado_id", table_name="notas")
