"""add_clerk_id_to_tenant

Revision ID: 3a081d414e04
Revises: 54bfed9c5a72
Create Date: 2026-06-22 23:41:43.885129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a081d414e04'
down_revision: Union[str, None] = '54bfed9c5a72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('clerk_id', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_tenants_clerk_id'), 'tenants', ['clerk_id'], unique=True)
    
    # Intenta borrar password_hash si existe (Limpieza post-migración a Clerk)
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns('tenants')]
    if 'password_hash' in columns:
        op.drop_column('tenants', 'password_hash')


def downgrade() -> None:
    op.drop_index(op.f('ix_tenants_clerk_id'), table_name='tenants')
    op.drop_column('tenants', 'clerk_id')
