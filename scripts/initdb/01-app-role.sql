-- The application connects as `medrecord_app`, a non-superuser role, because
-- superusers bypass Row-Level Security and RLS is what isolates one doctor's
-- records from another's. 21 migrations GRANT/REVOKE against this role, so
-- `alembic upgrade head` fails outright if it does not exist.
--
-- Postgres runs this file only on first initialisation of the data volume. To
-- re-run it on an existing checkout: docker compose down -v && docker compose up -d
CREATE ROLE medrecord_app WITH LOGIN PASSWORD 'apppassword';
GRANT CONNECT ON DATABASE medrecord TO medrecord_app;
