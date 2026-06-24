You are performing a repository cleanup. Apply all of the following changes in order. Do not modify any application code, Terraform infrastructure logic, or test logic — only the items listed here.

---

## STEP 1 — Critical: Remove Terraform state files from git tracking

Add the following lines to `.gitignore` if not already present:

```
*.tfstate
*.tfstate.backup
*.state
*.backup
```

Run `git rm --cached` on every `.state`, `.tfstate`, and `.tfstate.backup` file found in the `terraform/` directory. Do not delete the files from disk — only remove them from git tracking.

Commit with message: `chore: remove terraform state files from git tracking`

---

## STEP 2 — Delete scratch files at repo root

Delete these files entirely (they are personal debug notes, not documentation):

- `claudeAudit.md`
- `errorsCICD.md`
- `finalAudit.md`
- `fix.md`
- `notStagin.md`
- `prod.md`
- `security_audit_clerk_migration.md`
- `test_pydantic.py`
- `test_pydantic2.py`
- `test_secrets.sh`
- `empty_bucket.py`

---

## STEP 3 — Delete generated artifacts from git tracking

- Add `coverage.xml` to `.gitignore`
- Run `git rm --cached backend/coverage.xml`
- Add `terraform/modules/compute/dummy.zip` to `.gitignore`
- Run `git rm --cached terraform/modules/compute/dummy.zip`

---

## STEP 4 — Delete empty test placeholder

- Delete `tests/nom_compliance/` directory entirely (it contains only an empty `__init__.py`)

---

## STEP 5 — Minor code cleanup

- In `backend/app/main.py`, remove the duplicate `import traceback` (keep only the first occurrence)
- In `backend/app/core/config.py`, delete the `_settings()` wrapper function (lines ~82-83) — nothing imports it

---

## DO NOT touch

- `backend/app/models/consentimiento.py` or `aviso_privacidad.py` — keep them, they will be needed for NOM-004 consentimientos
- `backend/app/schemas/cita.py` — keep it
- Any application logic, routes, services, middleware, or Terraform infrastructure code
- Any file in `docs/architecture-decisions/`

---

## Verification checklist

After all changes are applied, confirm:

1. No `.state`, `.tfstate`, or `.tfstate.backup` files are tracked by git
2. `coverage.xml` and `dummy.zip` are in `.gitignore`
3. All scratch files listed in Step 2 are deleted
4. The duplicate `import traceback` is gone
5. `_settings()` is gone from `config.py`

Commit all remaining changes with message: `chore: repo cleanup pre-beta`