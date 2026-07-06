## CRITICAL (Launch Blocker)

### ❌ Live Clerk `sk_live_*` secret exposed in plaintext Terraform state — and NOT gitignored
**Files:** `terraform/state.json`, `terraform/state_fixed.json`, `terraform/state_fixed2.json`
**Evidence:** All three contain `"CLERK_SECRET_KEY": "sk_live_••••••••••••••••••••••••••••••••••••••••••"` in cleartext. `git check-ignore` returns nothing for these files — `.gitignore` only excludes `*.tfstate/*.tfstate.*`, and these are named `state.json`. They currently show as untracked in `git status`, meaning a single `git add .` publishes a live production auth secret to history.
**Actions required:** (1) Rotate the Clerk secret key immediately — it must be considered compromised. 
(2) Delete these files from the working tree. 
(3) Add `state*.json` / `*.state` / `plan.out` to `terraform/.gitignore`.

---

## HIGH (Before First Paying Customer)

### ❌ CORS allows localhost in production (environment value mismatch: "prod" ≠ "production")
**Files:** `terraform/prod.tfvars`, `terraform/modules/compute/main.tf`
**Evidence:** `prod.tfvars` sets `environment = "prod"`. The Lambda env builds CORS as `var.environment == "production" ? [prod-only] : [prod + "http://localhost:5173"]`. Since the value is `"prod"` (not `"production"`), the ternary falls to the else branch and ships `http://localhost:5173` into prod CORS — combined with `allow_credentials=True` in `app/main.py`. Note the rest of the app standardizes on `"prod"` (docs disable, HSTS, deletion_protection all check `"prod"`), so this one comparison is the outlier bug. (This is also why checklist item “environment = 'production'” reads as a mismatch — the canonical value is intentionally `"prod"` everywhere except this CORS line.)

### ❌ clerk_secret_key not marked sensitive = true
**File:** `terraform/modules/compute/variables.tf`
**Evidence:** `variable "clerk_secret_key" { type = string }` — no `sensitive = true`. The secret will render in terraform plan/apply output and CI logs (it is exported via `TF_VAR_clerk_secret_key` in `deploy.yml`).

### ❌ No API Gateway throttling (rate + burst) configured
**Files:** `terraform/modules/compute/main.tf`, all modules
**Evidence:** `grep` for throttl/method_settings/quota across `terraform/` returns nothing. The `aws_api_gateway_stage` has no `method_settings` block — no per-method or default rate/burst limits. DoS and runaway-cost exposure.

### ❌ Bare print() in Lambda handler (not structured JSON) + prints email/tracebacks
**File:** `backend/app/main.py`
**Evidence:** The `handler()` migration and `upgrade_tenant` branches use `print("Running Alembic migrations…")`, `print(err)` (full traceback), and `print(f"Upgrading tenant {email}…")`. Bypasses the JSON logger and writes a doctor email + stack traces to CloudWatch as unstructured text.

### ❌ Smoke test not wired into the production deploy
**Files:** `.github/workflows/deploy.yml`, `backend/scripts/smoke_test.py`
**Evidence:** `smoke_test.py` exists but is never invoked in `deploy.yml`. The CD flow ends at `deploy-frontend-production` with no post-deploy smoke/health gate — a broken deploy is marked "complete."

### ❌ audit.sh does not exist
**Files:** repo-wide
**Evidence:** No `audit*.sh` anywhere; the only shell scripts are `terraform/cleanup_rds.sh`, `terraform/scripts/{init,bootstrap-backend}.sh`, `scripts/dev_bootstrap.sh`. The referenced production-log-group audit script is absent.

### ❌ ADR 002 missing
**Files:** `docs/architecture-decisions/`
**Evidence:** Only `001-cifrado-columnas-vs-tde.md` and `003-firma-ecdsa-obligatoria.md` exist. `002-*` is absent — and `prodAudit.md` (item M5) already acknowledges this gap.

---

## MEDIUM (30 days)

### ⚠️ RDS CPU alarm uses wrong dimension — will never fire
**Files:** `terraform/modules/observability/main.tf`, `terraform/main.tf`, `terraform/modules/database/main.tf`
**Evidence:** The `aurora_cpu` alarm filters on `dimensions = { DBClusterIdentifier = var.db_cluster_id }` (`"medrecord-prod"`), but the database is an `aws_db_instance` (not an Aurora cluster). Instance metrics are published under `DBInstanceIdentifier`, so this alarm receives no data. (Lambda error alarm is correct, so the "≥1 alarm exists" check still passes.)

### ⚠️ CloudFront has no 502/503 custom error page
**File:** `terraform/modules/cdn/main.tf`
**Evidence:** Only `custom_error_response` for 403 and 404 (SPA routing → `/index.html`). No graceful-degradation page for origin 5xx (502/503).

### ⚠️ Lambda reserved_concurrent_executions neither set nor documented
**Files:** `terraform/modules/compute/main.tf`, `docs/`
**Evidence:** Not present in the `aws_lambda_function.api` config (defaults to -1/unreserved, per state files), and no doc justifies the omission. No protection against exhausting account concurrency or overwhelming RDS connections.

### ⚠️ One Alembic migration has a stub downgrade
**File:** `backend/alembic/versions/4f4145428368_ponytail_remove_dead_tables.py`
**Evidence:** AST check across all 16 migrations: only this one has a `downgrade()` body of `pass` (all others implement real reversals). A "remove dead tables" migration is irreversible as written.

---

## LOW (Nice to have)

### ⚠️ Placeholder alarm email in production
**File:** `terraform/prod.tfvars`
**Evidence:** `alarm_email = "admin@example.com"`. Alarms will notify a non-existent inbox.

### ⚠️ Onboarding null-UUID used during tenant INSERT, not only read-only lookup
**Files:** `backend/app/db/session.py`, `backend/app/api/v1/auth.py`
**Evidence:** `session.py` sets `app.current_tenant = 00000000-…` for the onboarding transaction, which then creates a `Tenant` (`auth.py` onboarding). Benign in practice — the tenants table has no `tenant_isolation` RLS policy — but the null tenant is not strictly "read-only" as the checklist assumes.

### ⚠️ Doc drift: dbChange.md describes Aurora Serverless v2; deployed DB is aws_db_instance
**Files:** `dbChange.md`, `terraform/modules/database/main.tf`
**Evidence:** Deployed DB is `aws_db_instance` (`db.t4g.small`). The multi-AZ / cost rationale is documented against the wrong engine, and the observability module inherits Aurora-cluster assumptions (see MEDIUM alarm bug).

### ⚠️ Untracked-but-unignored Terraform junk in working tree
**Files:** `terraform/plan.out`, `terraform/empty.py`, `terraform/empty_force.py`
**Evidence:** Not ignored; `plan.out` can also embed secrets.