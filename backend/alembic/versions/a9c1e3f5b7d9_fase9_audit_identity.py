"""Fase 9: bind immutable request audit rows to the authenticated identity/session.

Revision ID: a9c1e3f5b7d9
Revises: f6a8b0c2d4e6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a9c1e3f5b7d9"
down_revision: str | None = "f6a8b0c2d4e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audit_log", sa.Column("identity_provider_id", sa.String(length=128), nullable=True)
    )
    op.add_column("audit_log", sa.Column("session_id", sa.String(length=128), nullable=True))
    op.add_column(
        "audit_log",
        sa.Column(
            "factor_verification_age", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.create_index(
        "ix_audit_log_tenant_identity_timestamp",
        "audit_log",
        ["tenant_id", "identity_provider_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_tenant_identity_timestamp", table_name="audit_log")
    op.drop_column("audit_log", "factor_verification_age")
    op.drop_column("audit_log", "session_id")
    op.drop_column("audit_log", "identity_provider_id")
