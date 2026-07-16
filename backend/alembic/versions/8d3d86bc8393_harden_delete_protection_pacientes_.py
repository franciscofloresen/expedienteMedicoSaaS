"""harden_delete_protection_pacientes_tokens

Revision ID: 8d3d86bc8393
Revises: 5eb13dab23be
Create Date: 2026-07-14 20:21:14.867055

Belt-and-suspenders delete-protection to close the last two gaps found in the
grants audit:

  * pacientes — root of the clinical record (NOM-004 §5.14). Already REVOKE'd
    DELETE from the app role (a1b2c3d4e5f6) but lacked the owner/superuser-level
    trigger that notas/expedientes have. Add prevent_pacientes_deletion.
    Explicit database maintenance can still use TRUNCATE, which does not fire
    BEFORE DELETE triggers.

  * verification_tokens — anchors public verification/integrity of signed
    documents (NOM-024). It was created with GRANT ALL, so the app could delete
    a token and break a signed note's verification. REVOKE DELETE from the app
    role. No trigger: tokens are integrity infra, not clinical documents, and
    ops cleanup (TRUNCATE) must remain possible.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8d3d86bc8393"
down_revision: Union[str, None] = "5eb13dab23be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pacientes: add the owner/superuser-level DELETE block (REVOKE already exists).
    op.execute("DROP TRIGGER IF EXISTS prevent_pacientes_deletion ON pacientes")
    op.execute(
        """
        CREATE TRIGGER prevent_pacientes_deletion
        BEFORE DELETE ON pacientes
        FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion()
        """
    )

    # verification_tokens: app role must not delete signed-doc verification anchors.
    op.execute("REVOKE DELETE ON verification_tokens FROM medrecord_app")


def downgrade() -> None:
    op.execute("GRANT DELETE ON verification_tokens TO medrecord_app")
    op.execute("DROP TRIGGER IF EXISTS prevent_pacientes_deletion ON pacientes")
