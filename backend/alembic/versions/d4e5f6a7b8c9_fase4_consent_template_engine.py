"""fase4 motor versionado de plantillas de consentimiento

Revision ID: d4e5f6a7b8c9
Revises: b3d5e7f9c1a2
Create Date: 2026-07-15

Schema only (§1.5): the five legacy templates are published later by the audited
``import_consent_templates`` admin payload. The catalog is shared reference data (no
``tenant_id``, therefore no RLS); ``medrecord_app`` receives SELECT only.

Published content is immutable at the database boundary. A published version may only
transition to ``retirada``; changing its render content, field/signature rules, review
metadata or hash requires a new version. Existing consentimientos are never updated. New
ones snapshot the exact version through nullable ``plantilla_version_id`` while keeping
the legacy key/version/rendered-content snapshot.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "b3d5e7f9c1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TEMPLATES = "consentimiento_plantillas"
_VERSIONS = "consentimiento_plantilla_versiones"


def upgrade() -> None:
    op.create_table(
        _TEMPLATES,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("template_key", sa.String(80), nullable=False),
        sa.Column("categoria", sa.String(80), nullable=False),
        sa.Column("especialidad", sa.String(100)),
        sa.Column("procedimiento", sa.String(160)),
        sa.Column("estado", sa.String(20), nullable=False, server_default="activa"),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "actualizada_en",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("estado IN ('activa', 'retirada')", name="plantilla_estado_check"),
        sa.UniqueConstraint("template_key", name="uq_consentimiento_plantillas_template_key"),
    )
    op.create_index("ix_plantillas_especialidad", _TEMPLATES, ["especialidad"])
    op.create_index("ix_plantillas_procedimiento", _TEMPLATES, ["procedimiento"])

    op.create_table(
        _VERSIONS,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "plantilla_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{_TEMPLATES}.id", name="fk_plantilla_version_plantilla"),
            nullable=False,
        ),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("contenido", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "campos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("firmas_requeridas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "referencias_normativas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("estado", sa.String(20), nullable=False, server_default="borrador"),
        sa.Column("responsable_revision", sa.String(200)),
        sa.Column("revisada_en", sa.DateTime(timezone=True)),
        sa.Column("contenido_hash", sa.String(64), nullable=False),
        sa.Column("publicada_en", sa.DateTime(timezone=True)),
        sa.Column(
            "creada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.CheckConstraint(
            "estado IN ('borrador', 'publicada', 'retirada')",
            name="plantilla_version_estado_check",
        ),
        sa.UniqueConstraint("plantilla_id", "version", name="uq_plantilla_version"),
    )
    op.create_index("ix_plantilla_versiones_plantilla_id", _VERSIONS, ["plantilla_id"])
    op.create_index(
        "uq_plantilla_version_publicada",
        _VERSIONS,
        ["plantilla_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'publicada'"),
    )

    # Shared catalog: app reads, admin payload publishes. Default privileges otherwise
    # grant INSERT/UPDATE to medrecord_app, so reset explicitly to least privilege.
    for table in (_TEMPLATES, _VERSIONS):
        op.execute(f"REVOKE ALL ON TABLE {table} FROM medrecord_app")
        op.execute(f"GRANT SELECT ON TABLE {table} TO medrecord_app")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_published_consent_template_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.estado IN ('publicada', 'retirada') THEN
                    RAISE EXCEPTION 'Published consent template versions cannot be deleted';
                END IF;
                RETURN OLD;
            END IF;

            IF OLD.estado IN ('publicada', 'retirada') THEN
                IF OLD.plantilla_id IS DISTINCT FROM NEW.plantilla_id
                   OR OLD.version IS DISTINCT FROM NEW.version
                   OR OLD.nombre IS DISTINCT FROM NEW.nombre
                   OR OLD.contenido IS DISTINCT FROM NEW.contenido
                   OR OLD.campos IS DISTINCT FROM NEW.campos
                   OR OLD.firmas_requeridas IS DISTINCT FROM NEW.firmas_requeridas
                   OR OLD.referencias_normativas IS DISTINCT FROM NEW.referencias_normativas
                   OR OLD.responsable_revision IS DISTINCT FROM NEW.responsable_revision
                   OR OLD.revisada_en IS DISTINCT FROM NEW.revisada_en
                   OR OLD.contenido_hash IS DISTINCT FROM NEW.contenido_hash
                   OR OLD.publicada_en IS DISTINCT FROM NEW.publicada_en
                   OR (OLD.estado = 'retirada' AND NEW.estado <> 'retirada')
                   OR (OLD.estado = 'publicada' AND NEW.estado NOT IN ('publicada', 'retirada'))
                THEN
                    RAISE EXCEPTION 'Published consent template versions are immutable; create a new version';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER consentimiento_plantilla_version_immutable
        BEFORE UPDATE OR DELETE ON {_VERSIONS}
        FOR EACH ROW EXECUTE FUNCTION prevent_published_consent_template_modification()
        """
    )

    # Snapshot link for new emissions only. No backfill and no UPDATE to historical or
    # signed consentimientos; legacy key/version/rendered content remain authoritative.
    op.add_column(
        "consentimientos",
        sa.Column("plantilla_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_consentimientos_plantilla_version",
        "consentimientos",
        _VERSIONS,
        ["plantilla_version_id"],
        ["id"],
    )
    op.create_index(
        "ix_consentimientos_plantilla_version_id",
        "consentimientos",
        ["plantilla_version_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_consentimientos_plantilla_version_id", table_name="consentimientos")
    op.drop_constraint(
        "fk_consentimientos_plantilla_version", "consentimientos", type_="foreignkey"
    )
    op.drop_column("consentimientos", "plantilla_version_id")

    op.execute(
        f"DROP TRIGGER IF EXISTS consentimiento_plantilla_version_immutable ON {_VERSIONS}"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_published_consent_template_modification()")
    op.drop_table(_VERSIONS)
    op.drop_table(_TEMPLATES)
