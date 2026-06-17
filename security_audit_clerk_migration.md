# 🔍 Security Audit — Post-Clerk Migration

> **Date:** 12 June 2026  
> **Scope:** Full review of all PRODUCTION_AUDIT.md findings after the Clerk auth migration, plus new vulnerabilities introduced by the migration itself.  
> **Method:** Manual code review of backend middleware, routes, models, frontend services, and configuration.

---

## Executive Summary

The Clerk migration **resolved 5 of the 8 critical findings** from the original audit. However, it **introduced 3 new vulnerabilities** (2 high, 1 medium) and left **2 critical items still open**. The codebase is in a significantly better security posture than before, but is **not yet production-ready for real patient data**.

| Category | Count | Blocking Go-Live? |
|----------|-------|--------------------|
| 🟢 Fixed | 9 | — |
| 🟡 Partially Fixed / New Risk | 5 | Yes (3), No (2) |
| 🔴 Still Open | 5 | Yes (2), No (3) |

---

## Part 1: Original PRODUCTION_AUDIT.md Findings — Status Update

### 🟢 CRIT-01 — JWT Secret Hardcoded → **FIXED**

**File:** [security.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/core/security.py)

The hardcoded `LOCAL_JWT_SECRET = "medrecord-dev-secret-change-in-production"` has been **completely removed**. The current implementation (line 36-61) uses:
1. `JWT_DEV_SECRET` from env var (if configured).
2. Ephemeral `os.urandom(32)` per process (if not configured).
3. Production: Clerk RS256 via JWKS — no local secret needed.

**Verdict:** ✅ Properly remediated.

---

### 🟢 CRIT-02 — `.env.local` Committed to Git → **FIXED**

`.env.local` files are **not tracked** by Git. Verified via `git ls-files | grep .env`:
- Only `.env.example` files are tracked (templates without secrets).
- `.gitignore` correctly excludes `.env`, `.env.local`, `.env.*.local`.

**Verdict:** ✅ Properly remediated.

---

### 🟢 CRIT-03 — Tokens in `localStorage` (XSS → Session Hijack) → **FIXED**

The old `frontend/src/services/auth.ts` that stored tokens in `localStorage` has been **deleted entirely**. Clerk manages token storage internally using its own secure mechanisms. The frontend only calls `getToken()` from `@clerk/react` to get short-lived session tokens on demand — they are never persisted by our code.

The only `localStorage` usage remaining is in [useAutosave.ts](file:///Users/franciscofloresenriquez/expedienteMedico/frontend/src/hooks/useAutosave.ts) for draft clinical notes (non-sensitive form data, no tokens or PII).

**Verdict:** ✅ Properly remediated.

---

### 🟢 CRIT-04 — CORS `allow_headers=["*"]` → **FIXED**

**File:** [main.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/main.py#L119-L126)

```python
allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID"],
```

Explicit whitelist is now enforced.

> [!WARNING]
> `X-Tenant-ID` is in the whitelist because the dev fallback needs it. When the onboarding flow is complete and `X-Tenant-ID` is removed from the dev bypass, this header should also be removed from the CORS whitelist.

**Verdict:** ✅ Fixed (with a cleanup TODO for later).

---

### 🟢 CRIT-05 — No Rate Limiting on Auth Endpoints → **FIXED (by Clerk)**

Authentication is now **entirely delegated to Clerk**. Clerk provides:
- Built-in brute-force protection.
- CAPTCHA integration.
- Account lockout after failed attempts.
- Bot detection.

Our backend no longer has `/login` or `/register` endpoints. The `slowapi` limiter is still installed (line 107-112 of `main.py`) for future use on other endpoints.

**Verdict:** ✅ Delegated to Clerk, which handles this natively.

---

### 🟡 CRIT-06 — Dev Bypass via `X-Tenant-ID` Header → **PARTIALLY FIXED — NEW REGRESSION**

**File:** [tenant.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/middleware/tenant.py#L42-L77)

The `environment` default was correctly changed to `"production"` (fail-closed) in [config.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/core/config.py#L23). This is good.

However, **two new X-Tenant-ID bypass paths exist now:**

1. **Line 42-49:** When a valid JWT is present but has no `tenant_id` claim, the middleware falls back to `X-Tenant-ID` header **even in production** if the header is present and `environment != "development"` check only applies when the header is missing.

   ```python
   if not tenant_id:
       tenant_id = request.headers.get("X-Tenant-ID")  # ← CHECKED FIRST
       if not tenant_id and settings.environment != "development":  # ← ONLY BLOCKS IF HEADER IS ABSENT
           return JSONResponse(status_code=403, ...)
   ```

   > [!CAUTION]
   > **NEW VULNERABILITY (HIGH):** An authenticated user with a valid Clerk token (but no `tenant_id` in claims) can set `X-Tenant-ID` to ANY tenant UUID and access another doctor's patients. This is a **tenant isolation bypass** in production.

2. **Line 60-77:** The unauthenticated X-Tenant-ID bypass is properly guarded by `environment != "development"`. This is correct.

**Frontend side:** [api.ts](file:///Users/franciscofloresenriquez/expedienteMedico/frontend/src/services/api.ts#L38-L42) currently sends `X-Tenant-ID` on **every** dev request, even when a valid Clerk token is present. This is a temporary workaround but masks the vulnerability above.

---

### 🟢 CRIT-07 — No Autosave/Offline → **FIXED**

[useAutosave.ts](file:///Users/franciscofloresenriquez/expedienteMedico/frontend/src/hooks/useAutosave.ts) implements `localStorage`-based draft saving. [ConnectionStatus.tsx](file:///Users/franciscofloresenriquez/expedienteMedico/frontend/src/components/ConnectionStatus.tsx) shows an offline banner.

**Verdict:** ✅ Phase 1 remediation complete.

---

### 🔴 CRIT-08 — No CD Pipeline → **STILL OPEN**

No changes to the CI/CD pipeline. Still CI-only (lint + test + build). No `deploy.yml`, no staging environment, no rollback automation.

**Verdict:** ❌ Still open. Not related to Clerk migration but remains a go-live blocker.

---

### 🟢 IMP-01 — No UUID Validation in Path Params → **FIXED**

All route handlers now use `UUID` type for path parameters:
- `paciente_id: UUID` in [pacientes.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/api/v1/pacientes.py#L145)
- `nota_id: UUID` in [notas.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/api/v1/notas.py#L130)

FastAPI will automatically reject non-UUID values with a 422 Validation Error.

**Verdict:** ✅ Fixed.

---

### 🟢 IMP-02 — Missing Security Headers → **FIXED**

[SecurityHeadersMiddleware](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/main.py#L52-L78) adds:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-XSS-Protection: 1; mode=block`
- `Cache-Control: no-store`
- `Strict-Transport-Security` (production only)

> [!NOTE]
> `Content-Security-Policy` is still missing. It should be added at the CloudFront level for the SPA.

**Verdict:** ✅ Mostly fixed (CSP deferred to CloudFront).

---

### 🟢 IMP-03 — JWT Expiry of 24 Hours → **FIXED (by Clerk)**

Clerk session tokens expire in **60 seconds** by default and are silently refreshed by the `@clerk/react` SDK. This is far more secure than the previous 24-hour JWT.

**Verdict:** ✅ Delegated to Clerk.

---

### 🟢 IMP-04 — No MFA → **PARTIALLY FIXED (by Clerk)**

Clerk supports MFA (TOTP, SMS) out of the box. It is **available** but not **enforced** for this Clerk instance. For a medical SaaS handling patient data, MFA should be **required**.

**Verdict:** ⚠️ Available but needs to be **enforced** in the Clerk Dashboard settings.

---

### 🔴 IMP-09 — Structured Logging → **FIXED**

[main.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/main.py#L28-L46) configures `python-json-logger` with JSON output. All audit entries are logged as structured JSON.

**Verdict:** ✅ Fixed.

---

### 🔴 IMP-11 — Frontend Input Sanitization → **STILL OPEN**

No `dangerouslySetInnerHTML` found (good), but forms still lack client-side validation beyond what Pydantic enforces on the backend. No HTML sanitization library is used.

**Verdict:** ⚠️ Low risk since React escapes by default and backend validates. Not blocking.

---

### 🔴 MEJORA-07 — `password_hash` Column Still in `tenants` Table → **STILL OPEN**

**File:** [tenant.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/models/tenant.py#L26)

```python
password_hash: Mapped[str | None] = mapped_column(String(128))
```

With Clerk, this column is **vestigial and a liability**. If the database is compromised, the password hashes (even though bcrypt) are an unnecessary exposure surface. The `bcrypt` dependency is also still in `pyproject.toml`.

**Verdict:** ❌ Should be removed via Alembic migration + dependency cleanup.

---

### 🟢 MEJORA-08 — Missing `audit_log` Index → **FIXED**

[rls_init.sql](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/db/rls_init.sql#L144-L145) includes:
```sql
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_timestamp
    ON audit_log (tenant_id, timestamp DESC);
```

**Verdict:** ✅ Fixed.

---

### 🟢 MEJORA-09 — Audit Immutability Trigger Not Implemented → **FIXED**

[rls_init.sql](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/db/rls_init.sql#L122-L138) implements the trigger. We **confirmed it works** when we tried `DELETE FROM audit_log` and PostgreSQL blocked us with:
```
Audit log records cannot be modified or deleted (NOM-004/NOM-024 compliance)
```

**Verdict:** ✅ Confirmed working.

---

## Part 2: New Vulnerabilities Introduced by Clerk Migration

### 🔴 NEW-01 — Tenant Isolation Bypass via X-Tenant-ID in Authenticated Requests (HIGH)

**File:** [tenant.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/middleware/tenant.py#L42-L49)

**Description:** When a user has a valid Clerk JWT but no `tenant_id` in the token claims (which is the current state for all users since Clerk metadata isn't configured yet), the middleware falls back to the `X-Tenant-ID` header **without checking the environment**. In production, an attacker could:

1. Create a Clerk account (free signup).
2. Get a valid JWT.
3. Set `X-Tenant-ID: <victim-doctor-uuid>`.
4. Access the victim's patients.

**Mitigation:** The RLS policies in PostgreSQL provide a **defense-in-depth layer** — `SET LOCAL "app.current_tenant"` is set in [session.py](file:///Users/franciscofloresenriquez/expedienteMedico/backend/app/db/session.py#L78-L80), which means the database only returns rows matching the spoofed tenant. However, if the attacker knows a valid tenant UUID, they would see that tenant's data.

**Remediation:**
```python
# In tenant.py, line 42-49, replace with:
if not tenant_id:
    if settings.environment == "development":
        tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return JSONResponse(status_code=403,
            content={"detail": "Token sin tenant_id asociado"})
```

**Priority:** 🔴 P0 — Must fix before any production deployment.

---

### 🟡 NEW-02 — No Clerk User ↔ Tenant Mapping in Database (MEDIUM)

**Description:** There is **no database table** linking Clerk `user_id` (e.g., `user_3F1fR5Vm...`) to a `tenant_id`. The system currently relies on either:
- JWT claims (`tenant_id` in metadata) — not configured.
- `X-Tenant-ID` header — insecure bypass.

Without this mapping, there is **no authoritative source of truth** for which user belongs to which tenant.

**Remediation:** This is exactly what the proposed Onboarding flow solves. A `clerk_users` or a column `clerk_user_id` on `tenants` table is needed.

**Priority:** 🟡 P1 — Required before production, planned in Onboarding.

---

### 🟡 NEW-03 — `ClerkProvider` Missing Explicit `publishableKey` Prop (LOW)

**File:** [main.tsx](file:///Users/franciscofloresenriquez/expedienteMedico/frontend/src/main.tsx#L9)

```tsx
<ClerkProvider afterSignOutUrl="/">
```

The `publishableKey` prop is not explicitly passed. Clerk falls back to the `VITE_CLERK_PUBLISHABLE_KEY` env var, which works but makes the dependency implicit. If the env var is missing, the app will silently fail to initialize auth.

**Remediation:** Add explicit prop:
```tsx
<ClerkProvider publishableKey={import.meta.env.VITE_CLERK_PUBLISHABLE_KEY} afterSignOutUrl="/">
```

**Priority:** 🔵 Low — Works today, but makes deployment fragile.

---

## Part 3: Compliance Impact Assessment

| PRODUCTION_AUDIT Check | Before Clerk | After Clerk | Notes |
|------------------------|-------------|-------------|-------|
| NOM-004 §5.3 (Patient ID) | ✅ | ✅ | No change |
| NOM-004 §5.8 (Note authorship) | ✅ | ⚠️ | `medico_nombre` and `cedula` are now hardcoded defaults in `tenant.py` (`"Médico Titular"`, `"ND"`) until onboarding is built |
| NOM-024 Audit trail | ✅ | ✅ | `usuario_id` changed from UUID to VARCHAR(100) to support Clerk IDs — trigger still works |
| NOM-024 Encryption | ✅ | ✅ | Envelope encryption unchanged |
| LFPDPPP Consent | ⚠️ | ⚠️ | No change (still needs dedicated table) |

---

## Part 4: Prioritized Action Plan

| # | Finding | Severity | Effort | Action |
|---|---------|----------|--------|--------|
| 1 | NEW-01: X-Tenant-ID bypass in authenticated flow | 🔴 P0 | 30 min | Fix `tenant.py` guard logic |
| 2 | NEW-02: No user↔tenant mapping | 🟡 P1 | 4-6 hrs | Build Onboarding flow (already planned) |
| 3 | MEJORA-07: Remove `password_hash` column | 🟡 P1 | 1 hr | Alembic migration + remove `bcrypt` dep |
| 4 | IMP-04: Enforce MFA | 🟡 P1 | 15 min | Toggle in Clerk Dashboard |
| 5 | NEW-03: Explicit `publishableKey` | 🔵 P2 | 5 min | Add prop to `ClerkProvider` |
| 6 | CRIT-08: CD Pipeline | 🔴 P0 | 8 hrs | Build `deploy.yml` (unchanged from original audit) |
| 7 | CRIT-04 cleanup: Remove `X-Tenant-ID` from CORS after onboarding | 🔵 P2 | 5 min | After item #2 is done |

> [!IMPORTANT]
> **Item #1 (NEW-01) is the only new critical vulnerability** and should be fixed immediately. It can be done in a single edit to `tenant.py`.

---

## Conclusion

The Clerk migration was a **net positive** for security — it eliminated 5 critical findings (hardcoded secrets, localStorage tokens, no rate limiting, 24h JWTs, CORS wildcards). The primary risk introduced is the **tenant isolation bypass** in the middleware, which must be patched before any production deployment. The Onboarding flow (already planned) will close the remaining gaps.
