"""force_rls_consentimientos_recetas

Revision ID: 45fd65e2a92f
Revises: c8d9e0f1a2b3
Create Date: 2026-07-14 19:59:00.799051

Restore FORCE ROW LEVEL SECURITY on the clinical tables `consentimientos` and
`recetas`. The original RLS migration (a1b2c3d4e5f6) forced `consentimientos`,
but later migrations that recreated/added these tables
(f9b8c7d6e5a4 for consentimientos, f1e1d175c332 for recetas) enabled RLS and a
tenant-isolation policy but never re-applied FORCE. Without FORCE, RLS is not
enforced for a table's owner; the app connects as the non-owner `medrecord_app`
role so isolation still held, but §1.2 of the roadmap requires FORCE on every
clinical table as defense-in-depth. Idempotent DDL, runs in milliseconds.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '45fd65e2a92f'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE consentimientos FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE recetas FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE recetas NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE consentimientos NO FORCE ROW LEVEL SECURITY")
