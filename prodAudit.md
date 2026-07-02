# 🔒 CloudMedRecord — Security & Compliance Audit

**Date:** 2026-07-01
**Scope:** Full codebase — `/expedienteMedico`
**Status:** READ-ONLY — No changes made. Awaiting approval.

---

## ❌ CRITICAL — Block launch (3 items)

### C1. Environment string mismatch: `"prod"` vs `"production"`

The entire security posture hinges on this string comparison and it is wrong.

| What expects | What it gets | Consequence |
|---|---|---|
| `config.py` defaults to `"production"` | `prod.tfvars` sends `"prod"` | Mismatch |
| `main.py` — HSTS header check `!= "production"` | Gets `"prod"` | HSTS not set |
| `main.py` — Swagger docs disabled `!= "production"` | Gets `"prod"` | `/docs` exposed in prod |
| `tenant.py` — X-Tenant-ID gate `== "testing"` | Gets `"prod"` | ✅ Safe |
| `encryption.py` — mock encryption in `("development","testing")` | Gets `"prod"` | ✅ Safe |

> ⚠️ Swagger UI (`/docs`) and the full OpenAPI schema (`/openapi.json`) are publicly accessible in production, exposing every endpoint, parameter, and schema to attackers.

**Evidence:** `prod.tfvars` → `environment = "prod"` vs `config.py` → `environment: str = "production"`

**Fix:** Change `prod.tfvars` to `environment = "production"` — one line.

---

### C2. Terraform state files on disk — likely tracked in git history

Files containing full AWS infrastructure metadata:

| File | Size | Contains |
|---|---|---|
| `terraform/dev.state` | 185KB | VPC IDs, KMS ARNs, RDS endpoints, S3 buckets, AWS account ID |
| `terraform/local.state` | 175KB | Same |
| `terraform/local.state.*.backup` (×2) | 185KB each | Same |
| `terraform/terraform.tfstate` | 181B | Empty (safe) |

`.gitignore` covers `*.state` and `*.tfstate`, but if these were committed before the gitignore was added, they are still in git history.

**Fix:**
```bash
git ls-files terraform/*.state terraform/*.backup
# If any output → git rm --cached + rotate any exposed infrastructure secrets
```

---

### C3. `localhost:5173` in production CORS origins

The Lambda environment always includes `http://localhost:5173` in CORS origins, even in production.

```hcl
CORS_ORIGINS = "[\"https://${var.frontend_url}\", \"http://localhost:5173\"]"
```

**Risk:** Any attacker running a local dev server on port 5173 can make authenticated cross-origin requests to the production API.

**Fix:** Conditionally include localhost only when `var.environment != "production"`.

---

## ⚠️ HIGH — Fix before first paying customer (5 items)

### H1. Clerk `sk_test_*` secret key on disk

`backend/.env.local` contains a real Clerk test secret key (`sk_test_LKByaZNy09k...`). The file is gitignored, but may have been committed before the gitignore existed.

**Fix:**
```bash
git log --all -- backend/.env.local
# If any history → rotate the key in Clerk dashboard immediately
```

---

### H2. Empty-string `medico_cedula` bypass on digital signature

The DB has `nullable=False` on `cedula`, but an empty string `""` passes that constraint. No application-level guard exists before signing.

**Risk:** A note could be digitally signed without a real cédula profesional — NOM-004 non-compliance.

**Fix:** Add before `sign_note()`:
```python
if not medico_cedula or not medico_cedula.strip():
    raise HTTPException(400, "Cédula profesional requerida para firmar")
```

---

### H3. `"dev-user"` fallback for missing JWT `sub` claim

If a valid JWT token has no `sub` claim, the middleware silently assigns `user_id = "dev-user"`.

```python
request.state.user_id = claims.get("sub", "dev-user")
```

**Risk:** Shared identity across any token missing `sub`.

**Fix:**
```python
user_id = claims.get("sub")
if not user_id:
    raise HTTPException(status_code=401, detail="Token inválido: falta claim 'sub'")
request.state.user_id = user_id
```

---

### H4. `citas` table missing `FORCE ROW LEVEL SECURITY`

The Alembic migration enables RLS on `citas` but does not include `ALTER TABLE citas FORCE ROW LEVEL SECURITY`. The table owner (superuser) can bypass RLS. Also missing from `rls_init.sql`.

**Fix:** Add in a new Alembic migration:
```sql
ALTER TABLE citas FORCE ROW LEVEL SECURITY;
```

---

### H5. RDS snapshot export to S3 still a TODO

The 1825-day (5-year NOM-004) retention is documented as a TODO but not implemented.

```hcl
# TODO: Long-term retention (NOM-004) requires an Aurora/RDS snapshot export strategy to S3...
# TODO: ...MUST be implemented before the first paying customer goes live.
```

**Fix:** Implement the snapshot export Lambda + S3 lifecycle policy before accepting payment from any customer.

---

## ⚠️ MEDIUM — Fix within 30 days (6 items)

### M1. No dedicated `AuditMiddleware` class

Docs and README reference an `AuditMiddleware` class, but no such class exists. Structured JSON logging goes to CloudWatch via `pythonjsonlogger`, but there is no per-request who/what/when/IP audit trail middleware.

**Fix:** Either implement the middleware or update docs to reflect the current architecture (structured logs as audit trail).

---

### M2. `print()` statements in Lambda handler

Multiple `print()` calls in the migration/upgrade handlers. `traceback.format_exc()` could leak DB connection strings in CloudWatch.

**Fix:** Replace with `logger.error()` using structured fields. Strip connection strings from tracebacks.

---

### M3. KMS direct calls — no DEK cache (cost/latency note)

Every `encrypt_field()` / `decrypt_field()` call makes a direct KMS API call. Config has `dek_cache_ttl: int = 300` but it is never used. IAM grants `kms:GenerateDataKey` suggesting envelope encryption was planned.

**Risk at scale:** Cost ($0.03/10K calls), latency (5–20ms/call), and KMS throttling (5,500 req/s/key).

**Fix:** Either implement envelope encryption with cached DEKs, or accept the cost and remove the dead `dek_cache_ttl` config to avoid confusion.

---

### M4. Null UUID `00000000-...` as onboarding RLS context

Used as a fallback tenant context during onboarding when no real tenant exists yet.

**Risk:** Fragile pattern — if any real data accidentally uses this UUID, it would be visible during onboarding.

**Fix:** Acceptable for now if onboarding queries are read-only against the tenants table. Document the decision as an ADR or inline comment.

---

### M5. ADR 002 is missing

`docs/architecture-decisions/` contains `001` and `003`, but `002-*` does not exist.

**Fix:** Create `002-tenant-key-placeholder.md` documenting why `tenant_key.py` exists but is not used in the active encryption flow.

---

### M6. `clerk_secret_key` module variable not marked `sensitive`

Root module variable is `sensitive = true`, but the compute module variable is not. Terraform may log it in plan output at the module level.

**Fix:**
```hcl
variable "clerk_secret_key" {
  type      = string
  sensitive = true
}
```

---

## 💡 LOW — Nice to have (4 items)

### L1. `/openapi.json` bypasses auth in middleware

Even if `/docs` is disabled, FastAPI still serves the raw OpenAPI spec at `/openapi.json`. It is listed in `PUBLIC_PATHS`.

**Fix:** Remove `/openapi.json` from `PUBLIC_PATHS`, or gate it the same way as `/docs`.

---

### L2. Dead entries in `PUBLIC_PATHS`

`/api/v1/auth/register` and `/api/v1/auth/login` are listed as public paths but no corresponding route handlers exist.

**Fix:** Remove dead entries from `PUBLIC_PATHS` to reduce attack surface confusion.

---

### L3. `dummy.zip` generated by Terraform

Generated by `data "archive_file" "dummy"`. Covered by `.gitignore` — verify it is not tracked.

```bash
git ls-files terraform/modules/compute/dummy.zip
```

---

### L4. AWS account ID in `prod.tfvars`

ACM cert ARN in `prod.tfvars` exposes account ID `107759015501`. Low risk, but a data point for attackers.

**Fix:** Move to Secrets Manager or a CI/CD secret variable instead of a committed file.

---

## ✅ PASSED — 25 checks

| # | Check | Evidence |
|---|---|---|
| 1 | No `INSERT INTO audit_log` in app code | Zero hits across codebase |
| 2 | `canonical_serialize()` includes all required fields | `firma.py` |
| 3 | `/firmar` queries tenants table directly | `notas.py` |
| 4 | DELETE trigger on `notas` | Alembic migration + REVOKE |
| 5 | DELETE trigger on `expedientes` | Alembic migration + REVOKE |
| 6 | `encrypt_field()` / `decrypt_field()` on domicilio + antecedentes | `pacientes.py`, `expedientes.py` |
| 7 | `tenant_key.py` not in active encryption flow | Table dropped in migration; direct KMS used |
| 8 | `firma.py` — all 4 functions intact | `sign_note`, `verify_signature`, `_sign_with_kms`, `canonical_serialize` |
| 9 | pgaudit `log = 'read,write'` | `database/main.tf` |
| 10 | `backup_retention_period = 35` | `database/main.tf` |
| 11 | S3 lifecycle 1825-day TODO exists | `database/main.tf` |
| 12 | ADR 001 + 003 exist | `docs/architecture-decisions/` |
| 13 | RLS `SET LOCAL` in `session.py` | `session.py` |
| 14 | All patient tables have `tenant_id` | `paciente`, `expediente`, `nota`, `receta`, `cita` — all `nullable=False` |
| 15 | No raw SQL in production API routes | All ORM via SQLAlchemy + RLS session |
| 16 | No `terraform apply -auto-approve` | Plan artifact applied via `terraform apply tfplan` |
| 17 | Manual approval on prod apply | `environment: production` in `deploy.yml` |
| 18 | Plan/apply are separate jobs | `deploy.yml` — two distinct jobs |
| 19 | Aurora migration runbook referenced | `deploy.yml` |
| 20 | `.gitignore` covers required patterns | `*.tfstate`, `*.state`, `coverage.xml`, `.env` all covered |
| 21 | `deletion_protection = true` in prod | `database/main.tf` — conditional on `"prod"` ⚠️ see C1 |
| 22 | No `__debug__` routes | Zero hits |
| 23 | `upgrade_tenant.py` commits after Clerk OK | `upgrade_tenant.py` |
| 24 | `upgrade_tenant.py` is idempotent | Early return if same plan |
| 25 | X-Tenant-ID only in `testing` env | `tenant.py` |

---

## Scoreboard

| Severity | Count |
|---|---|
| ❌ CRITICAL — block launch | 3 |
| ⚠️ HIGH — before first customer | 5 |
| ⚠️ MEDIUM — 30 days | 6 |
| 💡 LOW — nice to have | 4 |
| ✅ PASSED | 25 |
| **Total checks** | **43** |

---

> **The 3 CRITICAL items (C1 environment mismatch, C2 state files in git, C3 localhost CORS) are all one-line fixes. They must be resolved before any production traffic touches this system.**

**Verdict: DO NOT LAUNCH until C1, C2, C3 are resolved.**