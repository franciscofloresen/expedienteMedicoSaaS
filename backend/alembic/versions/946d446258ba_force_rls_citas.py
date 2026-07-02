"""force_rls_citas

Revision ID: 946d446258ba
Revises: bb4e76bfb226
Create Date: 2026-07-01 19:48:23.333163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '946d446258ba'
down_revision: Union[str, None] = 'bb4e76bfb226'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE citas FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE citas NO FORCE ROW LEVEL SECURITY")
