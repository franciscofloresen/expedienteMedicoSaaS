-- ============================================================
-- MedRecord SaaS — Row-Level Security Initialization
-- Run once after schema creation. Idempotent (uses IF NOT EXISTS).
--
-- CRITICAL: The application must connect as role 'medrecord_app'
-- (NOT as superuser). Superusers bypass RLS policies entirely.
-- ============================================================

-- ── Enable and Force RLS on all tenant-scoped tables ──
-- FORCE ensures RLS applies even to the table owner

ALTER TABLE pacientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE pacientes FORCE ROW LEVEL SECURITY;

ALTER TABLE expedientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE expedientes FORCE ROW LEVEL SECURITY;

ALTER TABLE notas ENABLE ROW LEVEL SECURITY;
ALTER TABLE notas FORCE ROW LEVEL SECURITY;

ALTER TABLE consentimientos ENABLE ROW LEVEL SECURITY;
ALTER TABLE consentimientos FORCE ROW LEVEL SECURITY;

ALTER TABLE avisos_privacidad ENABLE ROW LEVEL SECURITY;
ALTER TABLE avisos_privacidad FORCE ROW LEVEL SECURITY;

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
-- Note: We do NOT force RLS on audit_log for the admin role

-- ── Tenant isolation policies ──
-- Each policy filters rows by matching tenant_id with the
-- session variable set by the application middleware:
--   SET LOCAL "app.current_tenant" = '<tenant-uuid>'

DO $$
BEGIN
    -- Pacientes
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_pacientes') THEN
        CREATE POLICY tenant_isolation_pacientes ON pacientes
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
    END IF;

    -- Expedientes
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_expedientes') THEN
        CREATE POLICY tenant_isolation_expedientes ON expedientes
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
    END IF;

    -- Notas
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_notas') THEN
        CREATE POLICY tenant_isolation_notas ON notas
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
    END IF;

    -- Consentimientos
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_consentimientos') THEN
        CREATE POLICY tenant_isolation_consentimientos ON consentimientos
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
    END IF;

    -- Avisos de privacidad
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_avisos') THEN
        CREATE POLICY tenant_isolation_avisos ON avisos_privacidad
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
    END IF;

    -- Audit log: read own rows only
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'audit_read_own') THEN
        CREATE POLICY audit_read_own ON audit_log
            FOR SELECT
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
    END IF;

    -- Audit log: anyone can insert (system logs admin actions)
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'audit_write_all') THEN
        CREATE POLICY audit_write_all ON audit_log
            FOR INSERT
            WITH CHECK (true);
    END IF;
END $$;

-- ── Application Role ──
-- Non-superuser role for the application. RLS is enforced.
-- NEVER grant this role superuser privileges.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medrecord_app') THEN
        CREATE ROLE medrecord_app LOGIN;
    END IF;
END $$;

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO medrecord_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO medrecord_app;

-- REVOKE DELETE on clinical tables (NOM compliance: no deletions)
REVOKE DELETE ON pacientes FROM medrecord_app;
REVOKE DELETE ON expedientes FROM medrecord_app;
REVOKE DELETE ON notas FROM medrecord_app;
REVOKE DELETE ON consentimientos FROM medrecord_app;
REVOKE DELETE ON audit_log FROM medrecord_app;
REVOKE DELETE ON avisos_privacidad FROM medrecord_app;

-- REVOKE UPDATE on audit_log (NOM-024: audit trail is append-only)
REVOKE UPDATE ON audit_log FROM medrecord_app;

-- Grant future tables too
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO medrecord_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO medrecord_app;


-- ============================================================
-- Audit Log Immutability Trigger
-- NOM-024: The audit trail MUST be immutable.
-- This trigger prevents UPDATE and DELETE at the database level,
-- providing defense-in-depth even if application code is compromised.
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'SECURITY VIOLATION: La tabla audit_log es inmutable (NOM-024). '
        'No se permiten UPDATE ni DELETE. Acción bloqueada: %',
        TG_OP;
END;
$$ LANGUAGE plpgsql;

-- Drop if exists to make this idempotent
DROP TRIGGER IF EXISTS audit_immutable ON audit_log;

CREATE TRIGGER audit_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_mutation();

-- ── Performance Index for Audit Queries ──
-- Composite index on (tenant_id, timestamp) for the most common
-- audit query pattern: "show me the last N events for this tenant"

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_timestamp
    ON audit_log (tenant_id, timestamp DESC);
