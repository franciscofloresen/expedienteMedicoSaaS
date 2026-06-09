# Project Review Actions

This document lists the necessary fixes, compliance gaps, and possible improvements for the [Nombre en Construcción] SaaS project. The current codebase has a strong prototype foundation, but it should not be treated as production-ready or compliance-ready until the critical items below are implemented and verified.

## Priority 0: Required Before Production

### Persist Audit Logs

- Write audit events to the `audit_log` table inside the backend, not only to CloudWatch logs.
- Keep CloudWatch structured logs as a secondary observability channel.
- Ensure failed requests, authentication failures, reads, writes, updates, and delete attempts are recorded.
- Include `request_id`, tenant, user, IP, user agent, route, status, and error details.
- Add database constraints or triggers that prevent audit rows from being updated or deleted by the application role.
- Add tests proving audit records are created for clinical-record access and mutation.

Relevant files:

- `backend/app/middleware/audit.py`
- `backend/app/models/audit.py`
- `backend/alembic/versions/`

### Complete Digital Signature Persistence

- Store all signature metadata returned by `sign_note`:
  - `firma_digital`
  - `firma_hash_contenido`
  - `firma_kms_key_id`
  - `firma_algoritmo`
  - `firmado_por`
  - `firmado_en`
  - `medico_nombre`
  - `medico_cedula`
  - `medico_especialidad`
- Set `es_editable = false` when a note is signed.
- Prevent updates to signed notes at the API and database level.
- Add a verification endpoint such as `GET /api/v1/notas/{id}/verificar-firma`.
- Persist the same canonical signing metadata needed by verification.
- Add tests for successful signing, duplicate signing, tampered content, and verification failure.

Relevant files:

- `backend/app/api/v1/notas.py`
- `backend/app/services/firma.py`
- `backend/app/models/nota.py`

### Fix KMS Signing Context

- Pass tenant and note metadata into KMS signing in the intended audit context.
- If using AWS KMS asymmetric signing, confirm whether `EncryptionContext` is supported for the selected KMS operation and document the actual behavior.
- If KMS signing cannot bind context cryptographically, include tenant, note ID, user ID, doctor snapshot, and timestamp in the canonical signed payload.
- Align README claims with the actual KMS implementation.

Relevant files:

- `backend/app/services/firma.py`
- `README.md`

### Move RLS Setup Into Migrations

- Add Alembic migration steps that enable and force RLS on tenant-scoped tables.
- Add Alembic migration steps that create tenant isolation policies.
- Add migration coverage for the application role permissions.
- Avoid relying on manually running `backend/app/db/rls_init.sql`.
- Add deployment documentation that confirms the application never connects as a superuser or owner role.

Relevant files:

- `backend/alembic/versions/`
- `backend/app/db/rls_init.sql`
- `backend/app/db/session.py`

### Remove Production Tenant Header Bypass

- Ensure the frontend never sends `X-Tenant-ID` in production builds.
- Replace the hardcoded tenant header with real Cognito access-token injection.
- Add an environment guard so development-only behavior is impossible when `VITE_ENV` or build mode is production.
- Add backend protection that rejects `X-Tenant-ID` unless `ENVIRONMENT=development`.

Relevant files:

- `frontend/src/services/api.ts`
- `backend/app/middleware/tenant.py`

### Implement Authentication and Registration

- Replace placeholder auth routes with real registration and onboarding.
- Create tenants, tenant keys, and Cognito users in one safe onboarding workflow.
- Generate the tenant DEK during tenant creation.
- Store doctor identity and professional license data as first-class tenant metadata.
- Add login/session handling in the frontend.
- Add MFA and token refresh UX if Cognito Hosted UI or Amplify is used.

Relevant files:

- `backend/app/api/v1/auth.py`
- `backend/app/services/encryption.py`
- `frontend/src/services/api.ts`

## Priority 1: Correctness and Build Fixes

### Fix Frontend Build

- Remove unused `React` imports from files using the automatic JSX runtime.
- Run `npm run build` and `npm run lint` after the cleanup.

Known failures:

- `frontend/src/App.tsx`
- `frontend/src/components/Layout.tsx`

### Fix Note Creation UX

- The frontend currently says a note was created and signed, but the create endpoint returns a pending unsigned note.
- Either call the signing endpoint after note creation or update the UI copy to say the note is pending signature.
- Prefer an explicit two-step clinical workflow:
  - Save draft note.
  - Review and sign note.
- Disable editing after signature.

Relevant files:

- `frontend/src/pages/Expediente.tsx`
- `frontend/src/services/api.ts`
- `backend/app/api/v1/notas.py`

### Use the Correct Local Python Environment

- The backend declares Python `>=3.12`, but local test execution used Python 3.8.
- Add a `.python-version`, `uv`, Poetry, or documented virtualenv setup.
- Make the README setup commands reproducible.
- Ensure `pydantic-settings` and dev dependencies are installed before running tests.

Relevant files:

- `backend/pyproject.toml`
- `README.md`

### Add Frontend CI

- The current GitHub Actions workflow does not build or lint the frontend.
- Add CI steps for:
  - `npm ci`
  - `npm run build`
  - `npm run lint`
- Cache npm dependencies.

Relevant files:

- `.github/workflows/ci.yml`
- `frontend/package.json`

### Fix Backend CI Gaps

- Ensure CI runs all test folders even when some directories are empty.
- Add tests for security and integration behavior instead of leaving placeholder test directories.
- Add a backend formatting step if `ruff format --check` is expected to pass.
- Add mypy only when type errors are being actively maintained.

Relevant files:

- `.github/workflows/ci.yml`
- `backend/tests/`
- `backend/pyproject.toml`

## Priority 2: Security and Compliance Hardening

### Protect Clinical Data Retention

- Replace hard delete of patients with soft delete or archival status.
- If patients without expedientes can be deleted, document why this is legally acceptable.
- Add database permission and API tests proving clinical records cannot be deleted.
- Add retention policies for records, audit logs, consent documents, and backups.

Relevant files:

- `backend/app/api/v1/pacientes.py`
- `backend/app/db/rls_init.sql`
- `terraform/modules/storage/main.tf`

### Strengthen Database Constraints

- Add `WITH CHECK` policies to RLS rules so inserted or updated rows must match `app.current_tenant`.
- Add triggers to keep tenant consistency across related rows, such as `expedientes.tenant_id = pacientes.tenant_id`.
- Add constraints for immutable signed notes.
- Add unique constraints for one active expediente per patient if that is a product requirement.

Relevant files:

- `backend/app/db/rls_init.sql`
- `backend/alembic/versions/`
- `backend/app/models/`

### Improve Sensitive Field Encryption

- Decide which fields are sensitive enough to encrypt beyond address and antecedentes.
- Consider encrypting phone, email, insurance number, clinical note body, diagnoses, and consent metadata.
- Add associated authenticated data to AES-GCM encryption, such as tenant ID, table, field, and record ID.
- Add key rotation workflow and tests.

Relevant files:

- `backend/app/services/encryption.py`
- `backend/app/models/paciente.py`
- `backend/app/models/nota.py`

### Harden JWT Validation

- Validate token use explicitly, for example `token_use == "access"`.
- Validate required claims such as `sub`, `custom:tenant_id`, and client ID.
- Handle Cognito key rotation and JWKS fetch failures with clear errors.
- Avoid synchronous HTTP calls in request paths if they become a latency issue.

Relevant files:

- `backend/app/core/security.py`
- `backend/app/middleware/tenant.py`

### CORS and API Configuration

- Move API base URL and allowed origins to environment-specific configuration.
- Avoid hardcoded localhost values in production bundles.
- Add explicit production CORS origins.
- Consider rejecting wildcard headers if not needed.

Relevant files:

- `backend/app/core/config.py`
- `backend/app/main.py`
- `frontend/src/services/api.ts`

### Logging and Privacy

- Ensure logs never include full clinical payloads, secrets, tokens, CURP, addresses, or diagnoses.
- Define a structured log schema.
- Add request IDs to API responses and logs.
- Add log retention and export policies.

Relevant files:

- `backend/app/middleware/audit.py`
- `backend/app/main.py`
- `terraform/modules/observability/main.tf`

## Priority 3: Product and UX Improvements

### Complete Patient Detail Workflow

- Add a patient detail page or panel that shows full demographic data.
- Allow editing address, phone, email, insurance, and occupation.
- Add validation for CURP format beyond length.
- Add duplicate detection for name/date of birth when CURP is missing.

Relevant files:

- `frontend/src/pages/Pacientes.tsx`
- `backend/app/api/v1/pacientes.py`

### Improve Medical Record Workflow

- Support multiple note types with type-specific required fields.
- Add draft, review, sign, and locked states.
- Add filters and search within note history.
- Show signature verification status and signer identity.
- Add printable/exportable clinical summary.

Relevant files:

- `frontend/src/pages/Expediente.tsx`
- `backend/app/api/v1/notas.py`
- `backend/app/core/nom_validator.py`

### Consent and Privacy Notice Workflow

- Implement endpoints and UI for privacy notice acceptance.
- Implement consent document upload, hashing, and storage.
- Show consent status in patient and expediente views.
- Add audit events for consent creation, viewing, and revocation.

Relevant files:

- `backend/app/models/consentimiento.py`
- `backend/app/models/aviso_privacidad.py`
- `docs/legal/`

### Replace Alerts With Proper UI States

- Replace browser `alert()` and `confirm()` with modal, toast, and inline error components.
- Show API validation errors next to the relevant fields.
- Add loading and disabled states for mutations.
- Add retry affordances for transient network failures.

Relevant files:

- `frontend/src/pages/Pacientes.tsx`
- `frontend/src/pages/Expediente.tsx`
- `frontend/src/components/`

### Responsive Layout

- The current frontend uses fixed sidebar and panel widths.
- Add responsive behavior for tablet and mobile.
- Make tables usable on small screens.
- Ensure the side panel does not overflow narrow viewports.

Relevant files:

- `frontend/src/index.css`
- `frontend/src/components/Layout.tsx`
- `frontend/src/pages/Pacientes.tsx`
- `frontend/src/pages/Expediente.tsx`

## Priority 4: Infrastructure and Operations

### Validate Terraform End to End

- Run `terraform fmt -check -recursive`.
- Run `terraform init -backend=false` and `terraform validate` for dev.
- Run Checkov locally or in CI and fix high-severity findings.
- Confirm module outputs and inputs line up across networking, security, storage, database, auth, compute, and observability modules.

Relevant files:

- `terraform/`
- `.github/workflows/ci.yml`

### Deployment Packaging

- Define how the FastAPI app is packaged for Lambda.
- Ensure dependencies are built for the Lambda runtime architecture.
- Add deployment artifact creation to CI/CD.
- Add frontend deployment to S3/CloudFront.

Relevant files:

- `terraform/modules/compute/main.tf`
- `.github/workflows/ci.yml`
- `backend/pyproject.toml`
- `frontend/package.json`

### Environment Management

- Add separate configuration for local, dev, staging, and production.
- Do not commit real secrets or environment-specific credentials.
- Add `.env.example` files for backend and frontend.
- Document required AWS resources and bootstrap steps.

Relevant files:

- `backend/app/core/config.py`
- `terraform/environments/dev/terraform.tfvars`
- `README.md`

### Observability Runbooks

- Add runbooks for:
  - API 5xx spike
  - KMS signing failure
  - database connection exhaustion
  - failed audit persistence
  - suspicious cross-tenant access attempt
  - failed backup or restore
- Link alarms to runbooks.

Relevant files:

- `docs/`
- `terraform/modules/observability/main.tf`

## Documentation Corrections

### Align README With Reality

- Mark implemented, partial, and planned features clearly.
- Avoid claiming full NOM-004, NOM-024, or LFPDPPP compliance until the implementation, tests, legal review, and operational controls support it.
- Separate architecture vision from current code status.
- Document local setup, test execution, and known limitations.

Relevant files:

- `README.md`
- `changes.md`

### Add Compliance Matrix

- Create a matrix mapping each compliance requirement to:
  - implementation file
  - test coverage
  - operational control
  - residual risk
  - owner/status
- Keep legal interpretation separate from technical implementation.

Suggested file:

- `docs/compliance_matrix.md`

## Suggested Implementation Order

1. Fix frontend build and add frontend CI.
2. Set up reproducible Python 3.12 backend environment.
3. Move RLS and role permissions into Alembic migrations.
4. Persist audit logs to the database.
5. Complete note signing persistence and verification.
6. Replace hardcoded frontend tenant header with real auth flow.
7. Implement tenant onboarding and key creation.
8. Add tests for audit, RLS, signing, auth, and retention.
9. Correct README claims and add a compliance matrix.
10. Harden Terraform and deployment pipeline.

## Current Verification Snapshot

The following checks were run during review:

- `frontend npm run build` failed because of unused `React` imports in `src/App.tsx` and `src/components/Layout.tsx`.
- `backend python -m pytest` failed locally because the shell used Python 3.8 while the project requires Python 3.12, and required dependencies such as `pydantic_settings` were unavailable in that interpreter.

