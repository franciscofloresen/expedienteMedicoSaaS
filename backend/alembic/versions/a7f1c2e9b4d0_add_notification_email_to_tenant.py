"""add notification_email column to tenants

Revision ID: a7f1c2e9b4d0
Revises: e3c4d5f6a7b8
Create Date: 2026-07-09 01:15:00.000000

Optional per-doctor override for where appointment (cita) notifications are
sent. When null, notifications fall back to `email`. Kept separate from the
unique identity `email` so it can be set freely (e.g. to a real inbox) without
colliding with the unique constraint.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7f1c2e9b4d0"
down_revision: Union[str, None] = "e3c4d5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("notification_email", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "notification_email")
