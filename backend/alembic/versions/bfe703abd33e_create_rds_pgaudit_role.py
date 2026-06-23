"""create_rds_pgaudit_role

Revision ID: bfe703abd33e
Revises: 3a081d414e04
Create Date: 2026-06-23 00:00:25.456053

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfe703abd33e'
down_revision: Union[str, None] = '3a081d414e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Creamos el rol necesario para pgaudit si no existe
    # Ignoramos error si ya existe manejando el bloque DO
    op.execute(
        """
        DO $$
        BEGIN
          CREATE ROLE rds_pgaudit;
        EXCEPTION WHEN duplicate_object THEN
          RAISE NOTICE 'Role rds_pgaudit already exists';
        END
        $$;
        """
    )
    # Otorgamos el rol al usuario de la aplicación para que pueda usar pgaudit
    # Nota: asume que 'medrecord_app' es el usuario de la DB (o el usuario que aplica la migración si es distinto)
    # Como el grant no da error si ya lo tiene, podemos correrlo directo
    op.execute("GRANT rds_pgaudit TO medrecord_app")


def downgrade() -> None:
    # Revocamos y borramos el rol
    op.execute("REVOKE rds_pgaudit FROM medrecord_app")
    op.execute("DROP ROLE IF EXISTS rds_pgaudit")
