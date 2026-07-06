# Security & Architecture Audit Fixes (July 2026)

All issues outlined in the `critical.md` and `prodAudit.md` audit reports have been fully addressed. Below is a complete summary of the work that was done across the repository to bring it into compliance and fix the underlying bugs.

## Phase 1: CRITICAL Issues (Launch Blockers) ✅

1. **Live Clerk Secrets in State**
   - We successfully deleted `terraform/state.json`, `terraform/state_fixed.json`, and `terraform/state_fixed2.json` to prevent them from being committed into the git history.
   - We updated `terraform/.gitignore` to explicitly ignore `*.state`, `state*.json`, and Terraform plan output (`plan.out`).
   > [!WARNING]
   > You must still go into the Clerk dashboard and rotate the exposed `sk_live_*` secret key immediately since the file previously existed on disk.

## Phase 1: HIGH Issues (Pre-Launch) ✅

1. **CORS Mismatch (localhost in prod)**
   - Modified `terraform/modules/compute/main.tf` to match `var.environment == "prod"` (instead of `"production"`), ensuring `http://localhost:5173` is never sent as an allowed origin to real users.
2. **Clerk Secret Missing `sensitive` Flag**
   - Added `sensitive = true` in `terraform/modules/compute/variables.tf` to prevent the key from spilling into GitHub Actions logs.
3. **No API Gateway Throttling**
   - We applied an `aws_api_gateway_method_settings` block in `terraform/modules/compute/main.tf` configuring a default rate limit of 100 requests per second and a burst limit of 50.
4. **Bare `print()` in Lambda Handler**
   - Replaced raw print statements with `logging.getLogger("medrecord.handler")` inside `backend/app/main.py`. This ensures proper CloudWatch JSON formatting. We also stripped out the raw traceback from the HTTP body response.
5. **Missing Audit Script**
   - Created `scripts/audit.sh` which executes an `aws logs filter-log-events` command. It is executable and ready to fetch JSON logs for auditing.
6. **ADR 002 Missing**
   - Created `docs/architecture-decisions/002-tenant-key-placeholder.md` to document why `tenant_key.py` was dropped in favor of direct KMS usage.

## Phase 1: MEDIUM Issues (30 days) ✅

1. **Aurora CPU Alarm Dimension Error**
   - Updated the CloudWatch alarm in `terraform/modules/observability/main.tf` to correctly use `DBInstanceIdentifier` for the `db.t4g.small` instance.
2. **CloudFront 502/503 Missing Pages**
   - Added custom error responses for `502` and `503` in `terraform/modules/cdn/main.tf` routing them to `/index.html` for graceful SPA degradation.
3. **Irreversible Alembic Downgrade**
   - The migration stub `4f4145428368_ponytail_remove_dead_tables.py` now throws a `NotImplementedError` rather than silently passing if someone attempts to run a downgrade.

## Phase 1: LOW Issues (Nice to Have) ✅

1. **Placeholder Alarm Email**
   - Updated `alarm_email` in `terraform/prod.tfvars` from `admin@example.com` to `franciscofloresenr@gmail.com`.
2. **Onboarding Null-UUID Fragility**
   - Added an inline comment to `backend/app/db/session.py` explaining that using a dummy UUID (`00000000-...`) is safe because the `tenants` table does not enforce `tenant_isolation` RLS policies.
3. **Documentation Drift**
   - Updated `dbChange.md` to correctly reflect that the migration was executed and the environment currently runs `aws_db_instance` (RDS), not Aurora Serverless v2.
4. **Untracked Terraform Junk**
   - The extra `empty.py` scripts and `plan.out` were deleted and fully added to `.gitignore`.

---

## Phase 2: Remaining prodAudit.md Fixes ✅

1. **Compromised Development Secret**
   - Confirmed that `backend/.env.local` was not in the remote repo and removed it locally to prevent any accidental commits.
2. **Hardcoded AWS Account ID**
   - Removed `acm_certificate_arn` from `terraform/prod.tfvars`. It is now securely passed in `deploy.yml` via the `TF_VAR_ACM_CERTIFICATE_ARN` GitHub secret.
3. **Public Path Overexposure**
   - Removed `/openapi.json` from `PUBLIC_PATHS` in `tenant.py` to prevent unauthorized access to the API schema.
   - Removed dead entries `/api/v1/auth/register` and `/api/v1/auth/login`.
4. **Dead Cache Variable**
   - Removed the unused `dek_cache_ttl` variable from `config.py` since direct KMS calls are being used.
5. **False Positives Verified**
   - **H2 (Cédula Bypass):** A check already exists in `notas.py` to block empty cédulas.
   - **H3 (JWT sub Bypass):** The JWT check is already enforced in `tenant.py`.
   - **H4 (Citas RLS):** The migration `946d446258ba_force_rls_citas.py` already implements `FORCE ROW LEVEL SECURITY`.
   - **H5 (Snapshot Export):** The export script `snapshot_export.tf` already exists and manages a 1825-day lifecycle policy.

---

## Phase 3: Post-Deploy Pipeline Adjustments ✅

1. **Lambda Concurrency Exhaustion Fix**
   - The `reserved_concurrent_executions` for the Lambda function was entirely removed in `terraform/modules/compute/main.tf` because the AWS account has a hard limit of 10 concurrent executions. Reserving any amount of concurrency would break the minimum unreserved pool requirement of 10.
2. **Smoke Test Dependencies Fix**
   - The smoke test step in `.github/workflows/deploy.yml` was moved from the frontend job to the backend job, and a `pip install .` step was added to ensure dependencies (like `pydantic` and `fastapi`) are available in the GitHub Actions runner before executing `scripts/smoke_test.py`.
3. **Code Quality (Ruff)**
   - Fixed out-of-order imports in `backend/app/main.py` using `ruff check --fix` and enforced clean code styling.
4. **Branch Cleanup**
   - Cleaned up the repository by deleting 22 fully-merged temporary `chore/`, `fix/`, and `feature/` branches both locally and remotely.
