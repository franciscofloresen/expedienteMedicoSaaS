"""ponytail: remove dead tables

Revision ID: 4f4145428368
Revises: f1e2d3c4b5a6
Create Date: 2026-06-27 21:27:08.093164

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4f4145428368'
down_revision: Union[str, None] = 'f1e2d3c4b5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ponytail: drop dead tables (speculative features, over-engineering)
    op.drop_table("audit_log")
    op.drop_table("tenant_keys")
    op.drop_table("consentimientos")
    op.drop_table("avisos_privacidad")


def downgrade() -> None:
    raise NotImplementedError("Migration is irreversible: dead tables cannot be restored.")
