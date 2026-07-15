"""revoke_delete_and_protect_recetas_consentimientos

Revision ID: 5eb13dab23be
Revises: 45fd65e2a92f
Create Date: 2026-07-14 20:14:39.313080

NOM-004 §5.14 (conservación): recetas and consentimientos are final clinical
documents and must not be hard-deletable. Both regressed to app-deletable when
later migrations granted broad privileges:

  * a1b2c3d4e5f6 REVOKE'd DELETE on consentimientos, but f9b8c7d6e5a4 recreated
    it with GRANT ALL (DELETE back).
  * f1e1d175c332 created recetas with GRANT ALL (DELETE from the start).

Bring both in line with notas/expedientes, which have BOTH role-level protection
(REVOKE DELETE) and a table trigger that blocks DELETE even for the table owner
or a superuser. Reuses the existing prevent_clinical_deletion() function.

This does NOT add an UPDATE-immutability trigger to consentimientos — that is a
Fase 5 design item that must be built to allow the verification_token_id write
before locking (to avoid repeating the firmar-500 bug).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5eb13dab23be"
down_revision: Union[str, None] = "45fd65e2a92f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("recetas", "consentimientos")


def upgrade() -> None:
    for table in _TABLES:
        # Role-level: the app can never issue a DELETE.
        op.execute(f"REVOKE DELETE ON {table} FROM medrecord_app")
        # Table-level: block DELETE even for the owner/superuser (defense in
        # depth, mirroring prevent_notas_deletion / prevent_expedientes_deletion).
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_deletion ON {table}")
        op.execute(
            f"""
            CREATE TRIGGER prevent_{table}_deletion
            BEFORE DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_clinical_deletion()
            """
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_deletion ON {table}")
        op.execute(f"GRANT DELETE ON {table} TO medrecord_app")
