# Doctor Demo Readiness Review

Date: 2026-06-07  
Goal: assess whether the local prototype is good enough to show doctors, and list what to change, improve, or defer.

## Verdict

The project is much closer to a presentable local prototype. The product direction is good: it now looks like a real clinical workflow instead of a generic CRUD app. The strongest parts are patient management, expediente creation, draft notes, signing/locking, local auth, audit logging direction, and the new local demo guide.

It is not show-ready yet. The frontend currently does not build, backend tests are not runnable in the current local Python environment, and some demo copy/data overstates security or compliance. For a doctor presentation, the product does not need AWS, but it does need to run reliably and avoid misleading claims.

My recommendation: do one cleanup sprint focused only on local demo reliability, truthful copy, and a polished end-to-end workflow.

## Current Quality

### Good

- The local-demo direction is correct. `README_LOCAL_DEMO.md` is exactly the kind of document this phase needs.
- Local registration now stores a password hash and login verifies it.
- Registration now creates a local tenant key, which prevents encrypted-field flows from failing immediately.
- The frontend has better UX: login/register, dashboard cards, modals, toasts, patient fields, and a clearer expediente view.
- Draft notes and signed/locked notes are the right model for doctors.
- There is now an audit endpoint, which can become a useful demo feature.
- CI no longer hides backend test failures with `|| true`.
- The architecture is still compatible with later AWS deployment, but the local version can move without cloud dependencies.

### Not Good Enough Yet

- `npm run build` currently fails due to an unused variable in `frontend/src/pages/Pacientes.tsx`.
- Backend tests cannot run locally because `python3.12` has no pytest/dev dependencies installed, and `python` is broken by the `.python-version`/pyenv mismatch.
- The seed script creates a mocked signed note that is displayed as valid, but it is not actually verifiable.
- The local demo guide still uses strong compliance language that may overclaim for a prototype.
- Some backend tests still use `Base.metadata.create_all` instead of Alembic migrations, so they do not prove migration/RLS/trigger behavior.
- The UI shows audit count, but not the actual audit events. A doctor cannot inspect the "bitacora" yet.

## Must Fix Before Showing Doctors

### 1. Fix the Frontend Build

Current failure:

```text
src/pages/Pacientes.tsx(26,44): error TS6133: 'isLoadingAudit' is declared but its value is never read.
```

Change:

- Either use `isLoadingAudit` in the dashboard card or remove it from the destructuring.
- Run `npm run build` again and treat a clean build as a hard demo gate.

Why:

- If the app cannot build, it is not ready for a presentation.

### 2. Make Local Setup Actually Reproducible

The new local guide is helpful, but it still needs verification from a clean database.

Change:

- Add a single script, for example `scripts/dev_bootstrap.sh`, that runs:
  - `docker compose up -d`
  - backend venv creation if missing
  - `pip install -e ".[dev]"`
  - `cp backend/.env.example backend/.env.local` if missing
  - `alembic upgrade head`
  - `python scripts/seed_demo_data.py`
- Add a reset command for demo rehearsals:
  - stop containers
  - delete volume
  - recreate DB
  - rerun migrations and seed

Why:

- You should be able to rehearse the demo on the day of the meeting without debugging local setup.

### 3. Fix the Python Environment Story

Current state:

- `python` fails because `.python-version` points to pyenv `3.12`, but that pyenv version is not installed.
- `python3.12` exists, but does not have `pytest`.

Change:

- Either remove `.python-version` for now, or set it to an installed exact version.
- Prefer documenting `python3.12 -m venv .venv`.
- After venv activation, every command should use `.venv/bin/python`.
- Add this to `README_LOCAL_DEMO.md`.

Why:

- This is a local prototype. The setup should be boring.

### 4. Replace Mock Signed Seed Data With Real Local Signatures

Current seed data creates a signed note with:

- random bytes as `firma_digital`
- `mockhash123` as `firma_hash_contenido`
- no real canonical signature process

Change:

- In `scripts/seed_demo_data.py`, use the real `sign_note()` function to create the seeded signed note.
- Store the returned signature metadata exactly like the API does.
- Or do not seed a signed note; seed only a draft and sign it live during the demo.

Recommended:

- Seed one draft note and sign it live. That is more convincing.

Why:

- The UI says "Firma Electronica Valida", but the seeded note is not actually valid. That is a trust problem.

### 5. Make Demo Copy Truthful

Change these labels:

- "Firma Electronica Valida (NOM-004)" -> "Nota firmada y bloqueada"
- "Registros inmutables en bitacora NOM-024" -> "Eventos recientes de bitacora"
- "Domicilio (Se guarda cifrado)" -> "Domicilio (cifrado local en demo)"
- Local demo text saying "fulfilling NOM-004" -> "designed to support NOM-004-style immutability"

Why:

- This is a prototype. Doctors will trust it more if the claims are precise.
- Avoid presenting legal compliance as finished before legal review and full test evidence.

### 6. Show the Audit Trail, Not Just a Count

The dashboard shows `auditLogs.length`, but the demo would be stronger if doctors can see the latest entries.

Change:

- Add a small "Bitacora reciente" table/card under the dashboard:
  - method
  - route
  - status
  - timestamp
  - success/failure
- Refresh after creating/updating/signing.

Why:

- Auditability is one of the core selling points. It should be visible.

### 7. Fix Patient Detail Fetching

The expediente page currently gets patient info by fetching all patients and finding by ID. That is okay for a tiny demo, but it is not good product behavior.

Change:

- Add `pacientesApi.getById(id)`.
- Use `GET /api/v1/pacientes/{id}` in the expediente page.

Why:

- It will show decrypted address and full patient details.
- It avoids fragile list-based lookup.

### 8. Make Draft Editing Complete

The backend has `PUT /api/v1/notas/{id}`, and the frontend service has `notasApi.update`, but verify the UI actually lets a doctor edit an existing draft and does not create duplicates.

Change:

- Add an "Editar borrador" button for unsigned notes.
- Pre-fill the side panel form with draft values.
- Save through `notasApi.update`.

Why:

- Doctors will expect to revise a note before signing.

## Security Assessment

### Acceptable for Local Prototype

- Local JWT auth with bcrypt password hashes is fine for a local demo.
- Local ECDSA signing is fine if clearly labeled as local-only.
- Local raw tenant keys are acceptable only if clearly documented as development behavior.
- The dev `X-Tenant-ID` bypass is acceptable only if environment-gated.

### Needs Improvement

- JWT secret is hardcoded. Move it to `LOCAL_JWT_SECRET` in `.env.local`.
- Auth/session storage uses `localStorage`. Fine for prototype, not production.
- Audit persistence logs errors but does not surface them. For demo, add an audit health indicator or show recent logs.
- RLS tests should use migrations, not `Base.metadata.create_all`, before you trust isolation claims.
- Public wording should avoid saying the prototype is compliant. Say "designed for compliance workflows."

## Missing for a Strong Doctor Demo

### Privacy and Consent

Doctors will ask about patient consent and privacy notices.

Add a simple prototype workflow:

- Privacy notice accepted: yes/no.
- Sensitive health data consent: yes/no.
- Timestamp and version.
- Display status in the expediente sidebar.

This can be local-only and simple. It does not need PDF generation yet.

### Clinical Summary or Print View

Add one doctor-friendly output:

- print expediente summary
- print signed note
- export simple PDF later

For now, browser print is enough.

### Search

Add patient search by:

- name
- CURP
- phone

This matters more to doctors than many backend compliance details during a demo.

### Better Empty/Error States

Add visible states for:

- backend offline
- no audit logs
- failed signature
- failed patient save
- missing expediente

The current toasts help, but doctor demos need stable screens, not only alerts.

## What I Would Delete or Defer

### Defer AWS Presentation

Do not lead with AWS. For doctors, lead with workflow:

- find patient
- create note
- sign and lock
- view audit
- protect privacy

Keep AWS in the appendix if they ask about deployment.

### Defer Terraform Fixes

Terraform quality matters later. It is not the blocker for doctor validation.

### Defer CI Artifact Packaging

The backend artifact zip is not useful for this local prototype stage. Keep CI simple:

- frontend build
- backend tests
- lint

### Defer AI, CFDI, Telemedicine

Do not mention these unless asked. They distract from the core value.

## Quality Rating

Current prototype quality: 6.5/10

After fixing build, setup, seed signatures, audit display, and wording: 8/10 for a doctor demo.

Security for prototype: 6/10

It is acceptable locally, but not production-secure. The biggest immediate fixes are moving the local JWT secret to env, truthful local signing labels, migration-backed tests, and audit visibility.

Architecture for prototype: 7.5/10

The structure is reasonable. The project has more AWS/production scaffolding than the demo needs, but that is not harmful if it does not get in the way.

## Recommended Next 2-Day Sprint

Day 1:

1. Fix the TypeScript build.
2. Verify local setup from a clean DB.
3. Fix seed script to use real local signing or seed only drafts.
4. Move local JWT secret to env.
5. Update misleading copy in frontend and `README_LOCAL_DEMO.md`.

Day 2:

1. Add recent audit table.
2. Add patient `getById` in frontend service and use it in expediente.
3. Confirm draft editing works end to end.
4. Add privacy/consent status placeholders.
5. Rehearse demo from reset DB twice.

## Demo Readiness Checklist

- [ ] `npm run build` passes.
- [ ] Backend starts from `README_LOCAL_DEMO.md` commands.
- [ ] Seed data runs twice safely or reset flow is documented.
- [ ] Login works with demo credentials.
- [ ] Wrong password fails.
- [ ] Patient creation works.
- [ ] Expediente creation works.
- [ ] Draft note creation works.
- [ ] Draft edit works.
- [ ] Signing locks the note.
- [ ] Signature verification works for any displayed signed note.
- [ ] Recent audit entries are visible in UI.
- [ ] UI does not overclaim legal compliance.
- [ ] No AWS credentials are needed.

## Verification Performed

- `frontend npm run build`: failed due to unused `isLoadingAudit` in `frontend/src/pages/Pacientes.tsx`.
- `backend python --version`: failed because pyenv expects version `3.12`, which is not installed under pyenv.
- `backend python3.12 --version`: succeeded with Python 3.12.9.
- `backend python3.12 -m pytest`: failed because pytest is not installed for that interpreter.

## Final Recommendation

The project is worth showing after a small cleanup sprint. Do not show it yet as-is. The story is strong, but the demo must be reliable and honest.

The best doctor-facing pitch is:

> "This is a local prototype of a Mexican clinical-record workflow: patients, expediente, draft notes, signature/lock, and audit trail. We are validating workflow and usability before deploying to AWS or making formal compliance claims."

