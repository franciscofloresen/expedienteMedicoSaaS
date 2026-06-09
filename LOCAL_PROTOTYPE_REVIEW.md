# Local Prototype Review

Date: 2026-06-04  
Goal: make the project work locally well enough to present to doctors before investing in AWS deployment.

## Short Verdict

The changes are directionally good for a doctor-facing prototype. The app now has the right shape: login/register, patient list, expediente view, draft notes, signing flow, soft delete, typed frontend API calls, modals, toasts, and a cleaner local-vs-production story.

For the immediate goal, I would shift priority away from AWS/Terraform/CI polish and toward one reliable local demo path. A doctor should be able to see this flow without setup friction:

1. Register doctor.
2. Create patient.
3. Create expediente.
4. Add note draft.
5. Review and sign note.
6. See signed/locked note with doctor identity, timestamp, and hash.
7. Show audit/access history or at least explain that it is being recorded.

Right now, the frontend build passes, but the local backend setup and authentication are still not solid enough for a smooth presentation.

## What Improved

- Frontend build now passes with `npm run build`.
- Auth screens make the prototype feel like a real product.
- The patient UI is much better: modal forms, delete confirmation, typed API calls, and toast feedback.
- The expediente flow is closer to how doctors think: drafts are separate from signed notes.
- The signing service now correctly acknowledges that local signing is not KMS and that KMS asymmetric signing does not use `EncryptionContext`.
- Signed note metadata persistence is much closer to what the project needs.
- RLS and immutability migrations are moving in the right direction.
- Soft delete is better than hard delete for a clinical-record product.

## Demo Blockers

### 1. Local Login Is Not Real

In `backend/app/api/v1/auth.py`, registration hashes the password but never stores it. Login then accepts any password for an existing tenant.

Problem:

- This is risky even for a prototype because the demo includes login/register.
- It will be awkward if someone asks whether the password is actually checked.
- The code comments say password hashing exists, but the behavior does not match.

Change:

- Add `password_hash` to the `tenants` table for local development.
- Store the hash during register.
- Verify the hash during login.
- Keep this clearly labeled as local auth only.

Alternative for fastest demo:

- Remove registration from the presentation.
- Seed one demo doctor account.
- Use fixed credentials shown in the README.

Recommended:

- Do both: implement real local password verification and provide a seeded demo doctor.

### 2. Local Setup Is Not One-Command Reproducible

The README still starts with AWS/Terraform setup. For this phase, that is the wrong first path.

Problems:

- The `.python-version` points pyenv to `3.12`, but this machine has `python3.12` available and pyenv does not have `3.12` installed.
- `python -m pytest` fails because pyenv cannot resolve `python`.
- `python3.12 -m pytest` fails because pytest is not installed.
- README mentions `pip install -r requirements.txt`, but this project uses `pyproject.toml`; there is no obvious local bootstrap command.
- Docker Compose creates only `medrecord`, while tests default to `medrecord_test`.

Change:

- Add a local-first setup section at the top of README:
  - `docker compose up -d`
  - `python3.12 -m venv .venv`
  - `source .venv/bin/activate`
  - `pip install -e ".[dev]"`
  - `cp .env.example .env.local`
  - `alembic upgrade head`
  - `python init_dev.py`
  - `uvicorn app.main:app --reload --port 8000`
  - `cd frontend && npm ci && npm run dev`
- Add `medrecord_test` creation to Docker setup or test setup.
- Either change `.python-version` to a version pyenv has, or document using `python3.12` directly.

### 3. Registration Does Not Create a Tenant Key

The register endpoint creates a tenant but does not create `tenant_keys`.

Problem:

- The moment the demo adds encrypted fields like address or antecedentes, create/update can fail with "Tenant encryption key not configured."
- For local demo, actual KMS is not needed, but the app needs a consistent local key strategy.

Change:

- During local registration, create a local `TenantKey`.
- Better: make local encryption deterministic enough for demo by using a local app secret or clearly mock encrypted fields.
- Do not pretend local encryption is KMS.

### 4. Audit Persistence Can Fail Silently

Audit persistence now writes to the database, which is good. But `_persist_audit` catches all exceptions and only logs them.

Problem:

- For a compliance demo, silent audit failure is dangerous.
- With dev bypass, `request.state.user_id = "local-dev-user"` is not a UUID, but audit SQL casts `usuario_id` to UUID. That can make audit inserts fail.

Change:

- Use a UUID for dev `user_id`, or allow `usuario_id` to be text.
- For local demo, expose an obvious audit health indicator.
- Add a simple `/api/v1/audit/recent` endpoint for the current tenant so the demo can show that access is recorded.
- In development, consider surfacing audit persistence errors loudly.

### 5. Tests Are Too Permissive

The new tests are a good start, but many assertions accept broad status ranges like `(200, 404, 500)` or only check that an endpoint is not `405`.

Problem:

- These tests will pass even when important behavior is broken.
- They do not prove signing, audit persistence, or RLS actually works.
- `Base.metadata.create_all` does not run Alembic migrations, so migration triggers/RLS are not being tested.

Change:

- For the prototype, write fewer but stricter integration tests:
  - register doctor
  - login with correct password succeeds
  - login with wrong password fails
  - create patient succeeds
  - create expediente succeeds
  - create note draft succeeds
  - sign note succeeds
  - update signed note fails
  - verify signature returns valid
  - audit row exists after patient/expediente/note access
- Run Alembic migrations in tests, not only `Base.metadata.create_all`.
- Remove `|| true` from CI test steps. It hides failures.

## What I Would Change Before Showing Doctors

### Make It a Local Demo Product, Not a Cloud Architecture Demo

For the presentation, the app should avoid AWS language unless the doctor asks about deployment.

Change UI copy:

- "Firma con KMS" -> "Firmar y bloquear nota"
- "Antecedentes (KMS)" -> "Antecedentes"
- "Firma Electrónica Válida (NOM-004)" -> "Nota firmada y bloqueada"

Reason:

- Locally, signing uses an ephemeral local ECDSA key, not KMS.
- Calling it "válida NOM-004" may overclaim. The prototype can say "bloqueada" and "verificable" without implying legal certification.

### Add Demo Data

Doctors should not start from an empty app in a presentation.

Add a local seed script that creates:

- One demo doctor.
- Three patients.
- One patient with an expediente and two signed notes.
- One patient with a draft note.
- One patient with no expediente yet.

This lets you demonstrate the product in two ways:

- "Here is what a real day looks like."
- "Now I will create a new patient from scratch."

### Add a Doctor-Facing Dashboard

The current first screen is the patient list, which is acceptable. But for demos, a small dashboard would help:

- Patients total.
- Draft notes pending signature.
- Expedientes missing consent/privacy notice.
- Recent patients.
- Recent signed notes.

Keep it simple. Do not build analytics yet.

### Add a Visible Compliance Checklist Per Patient

This would be a strong differentiator in front of doctors.

For each patient/expediente show:

- Datos de identificación completos.
- Expediente creado.
- Aviso de privacidad accepted.
- Consentimiento de datos sensibles accepted.
- Notas firmadas.
- Pendientes de firma.

Even if privacy/consent is mocked in the first demo, the UI should show where it will live.

### Add Draft Editing or Remove Edit State

`Expediente.tsx` has `editingNota`, but the mutation still creates a new note and includes a comment saying update is missing.

Change:

- Either implement `notasApi.update` and true draft editing.
- Or delete `editingNota` until it exists.

For a local prototype, I would implement draft editing because doctors will expect to correct a note before signing.

### Improve Patient Data Fields for Demo Credibility

Current patient creation is too minimal for a medical-record demo.

Add to the modal:

- telefono
- email
- domicilio
- ocupacion
- alergias or antecedentes quick field

You do not need every NOM field in the first screen, but doctors need to see enough clinical context to trust the product.

### Add a Print or Export Preview

For doctors, a record system feels real when they can produce something:

- Print clinical summary.
- Export signed note as PDF preview.
- Copy patient summary.

For prototype, a browser print view is enough.

## What I Would Delete or Defer

### Defer AWS Claims in README for the Demo

Do not lead the local prototype docs with Terraform, Aurora, WAF, KMS, and CloudFront. Keep that as "future production deployment."

For now, add:

- `README_LOCAL_DEMO.md`
- or a top-level "Local Prototype" section before the AWS section.

### Delete `|| true` From CI

CI that passes while tests fail is worse than no CI for engineering confidence.

If tests are not ready, mark jobs as experimental or skip them explicitly. Do not hide failures.

### Defer Terraform Work

Terraform can stay in the repo, but do not spend the next iteration there. The presentation risk is not "we lack WAF"; it is "the local product flow breaks."

### Defer AI, Telemedicine, CFDI, and AWS Deployment

None of these should be in the doctor demo unless the core flow is stable.

The current demo should sell:

- speed
- clarity
- signed/locked notes
- privacy posture
- auditability
- low cost

## Local Prototype Acceptance Criteria

Before presenting, I would require:

- `npm run build` passes.
- Backend starts from clean clone using documented commands.
- Local database starts with Docker Compose.
- Alembic migrations run successfully.
- Seed script creates demo doctor and sample data.
- Register/login works and wrong password fails.
- Create patient works.
- Create expediente works.
- Create draft note works.
- Edit draft note works.
- Sign note works.
- Signed note cannot be edited.
- Signature verification endpoint returns `valid: true`.
- Patient soft delete hides patient from list.
- Audit rows are created and can be shown.
- No UI says "KMS" during local signing.

## Verification Performed

- `frontend npm run build`: passed.
- `backend python -m pytest`: blocked because pyenv points to `3.12`, but pyenv does not have that version installed.
- `backend python3.12 -m pytest`: blocked because `pytest` is not installed for that interpreter.

## Recommended Next Sprint

1. Fix local auth persistence and password verification.
2. Add a one-command local setup path and seed data.
3. Make audit persistence reliable for local UUID values.
4. Implement draft note editing.
5. Remove misleading KMS/NOM-valid copy from local UI.
6. Add a simple audit/recent endpoint or audit panel.
7. Add strict end-to-end integration tests for the demo flow.

After those are done, the prototype should be good enough to put in front of doctors and ask practical workflow questions.

