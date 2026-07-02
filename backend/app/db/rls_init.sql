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

ALTER TABLE recetas ENABLE ROW LEVEL SECURITY;
ALTER TABLE recetas FORCE ROW LEVEL SECURITY;

ALTER TABLE citas ENABLE ROW LEVEL SECURITY;
ALTER TABLE citas FORCE ROW LEVEL SECURITY;


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

    -- Recetas
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_recetas') THEN
        CREATE POLICY tenant_isolation_recetas ON recetas
            USING (tenant_id = current_setting('app.current_tenant')::uuid);
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
REVOKE DELETE ON recetas FROM medrecord_app;

-- Grant future tables too
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO medrecord_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO medrecord_app;

