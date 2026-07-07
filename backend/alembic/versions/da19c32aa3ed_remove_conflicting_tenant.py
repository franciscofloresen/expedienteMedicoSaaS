"""remove_conflicting_tenant

Revision ID: da19c32aa3ed
Revises: 946d446258ba
Create Date: 2026-07-06 21:20:11.391798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'da19c32aa3ed'
down_revision: Union[str, None] = '946d446258ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM tenants WHERE cedula = '9623568';")


def downgrade() -> None:
    pass
