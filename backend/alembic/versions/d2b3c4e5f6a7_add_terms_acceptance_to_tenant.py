"""add terms acceptance columns to tenants

Revision ID: d2b3c4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-07-06 22:45:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2b3c4e5f6a7"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("terms_version", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "terms_version")
    op.drop_column("tenants", "terms_accepted_at")
