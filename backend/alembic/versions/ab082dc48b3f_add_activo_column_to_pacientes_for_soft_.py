"""Add activo column to pacientes for soft delete

Revision ID: ab082dc48b3f
Revises: a1b2c3d4e5f6
Create Date: 2026-06-04 13:11:09.320576

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab082dc48b3f"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pacientes",
        sa.Column(
            "activo", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_column("pacientes", "activo")
    # ### end Alembic commands ###
