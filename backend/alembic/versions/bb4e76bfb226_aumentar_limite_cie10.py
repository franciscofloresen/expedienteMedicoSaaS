"""aumentar_limite_cie10

Revision ID: bb4e76bfb226
Revises: f1e1d175c332
Create Date: 2026-07-01 00:32:32.011748

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb4e76bfb226'
down_revision: Union[str, None] = 'f1e1d175c332'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('notas', 'diagnostico_cie10',
               existing_type=sa.String(length=10),
               type_=sa.String(length=255),
               existing_nullable=True)


def downgrade() -> None:
    op.alter_column('notas', 'diagnostico_cie10',
               existing_type=sa.String(length=255),
               type_=sa.String(length=10),
               existing_nullable=True)
