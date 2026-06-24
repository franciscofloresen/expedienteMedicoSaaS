"""clinical_records_immutability

Revision ID: f1e2d3c4b5a6
Revises: bfe703abd33e
Create Date: 2026-06-24 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1e2d3c4b5a6'
down_revision: Union[str, None] = 'bfe703abd33e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
    CREATE OR REPLACE FUNCTION prevent_clinical_deletion()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'Clinical records are immutable';
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
    DROP TRIGGER IF EXISTS prevent_notas_deletion ON notas;
    CREATE TRIGGER prevent_notas_deletion
    BEFORE DELETE ON notas
    FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion();
    """)

    op.execute("""
    DROP TRIGGER IF EXISTS prevent_expedientes_deletion ON expedientes;
    CREATE TRIGGER prevent_expedientes_deletion
    BEFORE DELETE ON expedientes
    FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS prevent_notas_deletion ON notas;")
    op.execute("DROP TRIGGER IF EXISTS prevent_expedientes_deletion ON expedientes;")
    op.execute("DROP FUNCTION IF EXISTS prevent_clinical_deletion();")
