"""Add RLS policies, audit model expansion, and immutability controls

Revision ID: a1b2c3d4e5f6
Revises: 5a379e6d412d
Create Date: 2026-06-04 06:30:00.000000

This migration:
1. Adds request-level fields to audit_log (request_id, method, path, etc.)
2. Makes entity-level fields nullable (for request-level entries)
3. Removes the accion CHECK constraint (request entries don't have it)
4. Enables and forces RLS on all tenant-scoped tables
5. Creates tenant isolation policies WITH CHECK clauses
6. Creates the medrecord_app application role with least-privilege permissions
7. Adds an immutability trigger on audit_log (prevents UPDATE/DELETE)
8. Adds an immutability trigger on signed notes (prevents UPDATE when es_editable=false)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '5a379e6d412d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ──────────────────────────────────────────────
    # 1. Expand audit_log for request-level entries
    # ──────────────────────────────────────────────
    op.add_column('audit_log', sa.Column('request_id', sa.String(36), nullable=True))
    op.add_column('audit_log', sa.Column('method', sa.String(10), nullable=True))
    op.add_column('audit_log', sa.Column('path', sa.String(500), nullable=True))
    op.add_column('audit_log', sa.Column('status_code', sa.Integer(), nullable=True))
    op.add_column('audit_log', sa.Column('duration_ms', sa.Float(), nullable=True))
    op.create_index('ix_audit_log_request_id', 'audit_log', ['request_id'])

    # Make entity-level fields nullable (they're absent in request-level entries)
    op.alter_column('audit_log', 'tabla', nullable=True)
    op.alter_column('audit_log', 'registro_id', nullable=True)
    op.alter_column('audit_log', 'accion', nullable=True)

    # Drop the old accion CHECK constraint (request entries don't use it)
    op.drop_constraint('audit_log_accion_check', 'audit_log', type_='check')

    # ──────────────────────────────────────────────
    # 2. Enable and Force RLS on all tenant-scoped tables
    # ──────────────────────────────────────────────
    tenant_tables = ['pacientes', 'expedientes', 'notas', 'consentimientos', 'avisos_privacidad']

    for table in tenant_tables:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')

    # Enable RLS on audit_log (but don't FORCE — admin needs full access)
    op.execute('ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY')

    # ──────────────────────────────────────────────
    # 3. Create tenant isolation policies WITH CHECK
    # ──────────────────────────────────────────────
    # WITH CHECK ensures inserts/updates ALSO must match the current tenant.
    # USING filters reads; WITH CHECK filters writes.
    for table in tenant_tables:
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"""
            CREATE POLICY {policy_name} ON {table}
                USING (tenant_id = current_setting('app.current_tenant')::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)
        """)

    # Audit log: read own tenant's rows only
    op.execute("""
        CREATE POLICY audit_read_own ON audit_log
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant')::uuid)
    """)

    # Audit log: anyone can insert (system logs requests from all tenants)
    op.execute("""
        CREATE POLICY audit_write_all ON audit_log
            FOR INSERT
            WITH CHECK (true)
    """)

    # ──────────────────────────────────────────────
    # 4. Create application role with least-privilege
    # ──────────────────────────────────────────────
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medrecord_app') THEN
                CREATE ROLE medrecord_app LOGIN;
            END IF;
        END $$
    """)

    # Grant necessary permissions
    op.execute('GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO medrecord_app')
    op.execute('GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO medrecord_app')

    # REVOKE DELETE on clinical tables (NOM compliance: no hard deletions)
    clinical_tables = ['pacientes', 'expedientes', 'notas', 'consentimientos',
                       'avisos_privacidad', 'audit_log']
    for table in clinical_tables:
        op.execute(f'REVOKE DELETE ON {table} FROM medrecord_app')

    # REVOKE UPDATE on audit_log (append-only)
    op.execute('REVOKE UPDATE ON audit_log FROM medrecord_app')

    # Grant permissions on future tables too
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE ON TABLES TO medrecord_app
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE ON SEQUENCES TO medrecord_app
    """)

    # ──────────────────────────────────────────────
    # 5. Audit immutability trigger
    # ──────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'Audit log records cannot be modified or deleted (NOM-004/NOM-024 compliance)';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_modification()
    """)

    # ──────────────────────────────────────────────
    # 6. Signed note immutability trigger
    # ──────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_signed_note_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.es_editable = false THEN
                RAISE EXCEPTION 'Signed medical notes cannot be modified (NOM-004 compliance). Use an amendment note instead.';
                RETURN NULL;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER notas_signed_immutable
        BEFORE UPDATE ON notas
        FOR EACH ROW
        EXECUTE FUNCTION prevent_signed_note_modification()
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute('DROP TRIGGER IF EXISTS notas_signed_immutable ON notas')
    op.execute('DROP FUNCTION IF EXISTS prevent_signed_note_modification()')
    op.execute('DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log')
    op.execute('DROP FUNCTION IF EXISTS prevent_audit_modification()')

    # Drop RLS policies
    tenant_tables = ['pacientes', 'expedientes', 'notas', 'consentimientos', 'avisos_privacidad']
    for table in tenant_tables:
        op.execute(f'DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')

    op.execute('DROP POLICY IF EXISTS audit_read_own ON audit_log')
    op.execute('DROP POLICY IF EXISTS audit_write_all ON audit_log')
    op.execute('ALTER TABLE audit_log DISABLE ROW LEVEL SECURITY')

    # Revoke role permissions (role itself may be in use, leave it)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medrecord_app') THEN
                REVOKE ALL ON ALL TABLES IN SCHEMA public FROM medrecord_app;
                REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM medrecord_app;
            END IF;
        END $$
    """)

    # Drop new audit columns
    op.drop_index('ix_audit_log_request_id', table_name='audit_log')
    op.drop_column('audit_log', 'duration_ms')
    op.drop_column('audit_log', 'status_code')
    op.drop_column('audit_log', 'path')
    op.drop_column('audit_log', 'method')
    op.drop_column('audit_log', 'request_id')

    # Restore nullable constraints
    op.alter_column('audit_log', 'tabla', nullable=False)
    op.alter_column('audit_log', 'registro_id', nullable=False)
    op.alter_column('audit_log', 'accion', nullable=False)

    # Restore CHECK constraint
    op.execute("""
        ALTER TABLE audit_log ADD CONSTRAINT audit_log_accion_check
            CHECK (accion IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE'))
    """)
