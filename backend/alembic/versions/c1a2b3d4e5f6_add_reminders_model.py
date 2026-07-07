"""add reminders model

Revision ID: c1a2b3d4e5f6
Revises: 946d446258ba
Create Date: 2026-07-06 22:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "946d446258ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("paciente_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'dismissed')", name="reminders_status_check"
        ),
        sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reminders_tenant_id"), "reminders", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_reminders_paciente_id"), "reminders", ["paciente_id"], unique=False
    )

    # --- RLS Enforcement (tenant isolation, mirrors other tenant-scoped tables) ---
    op.execute("ALTER TABLE reminders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reminders FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON reminders
        USING (tenant_id = current_setting('app.current_tenant')::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)
    """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON reminders TO medrecord_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON reminders")
    op.drop_index(op.f("ix_reminders_paciente_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_tenant_id"), table_name="reminders")
    op.drop_table("reminders")
