"""ponytail_recetas_rls_perms

Revision ID: f1e1d175c332
Revises: e937940d8de9
Create Date: 2026-06-27 23:22:05.437855

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1e1d175c332'
down_revision: Union[str, None] = 'e937940d8de9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Grant perms to medrecord_app for new tables
    op.execute("GRANT ALL ON TABLE recetas TO medrecord_app")
    op.execute("GRANT SELECT ON TABLE cie10 TO medrecord_app")
    
    # Enable RLS on recetas
    op.execute("ALTER TABLE recetas ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_recetas ON recetas 
        FOR ALL 
        USING (tenant_id = current_setting('app.current_tenant')::uuid)
        """
    )



def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy_recetas ON recetas")
    op.execute("ALTER TABLE recetas DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE recetas FROM medrecord_app")
    op.execute("REVOKE SELECT ON TABLE cie10 FROM medrecord_app")
