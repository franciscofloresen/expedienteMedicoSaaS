I've fully explored your codebase. Here's my assessment:                                                      

---
                                                                                                                
## ✅ Context Loaded — CloudMedRecord SaaS                                                                    
                                                                                                                
I've read every file in the backend. Here's what I see and the rules I'll follow:                             
                                                                                                                
### Architecture Summary                                                                                      
                                                                                                                
| Layer | Implementation | Status |
| :--- | :--- | :--- |
| Auth | Clerk JWT (RS256 prod / HS256 dev) via `security.py` | ✅ Working |
| Tenant isolation | RLS via `SET LOCAL` in `session.py` + `medrecord_app` role | ✅ Solid |
| Encryption | Direct KMS `encrypt` / `decrypt` (no DEK cache) in `encryption.py` | ✅ Correct |
| Signing | ECDSA P-256 via KMS in `firma.py` | ✅ Correct |
| DB audit | pgAudit + CloudTrail (middleware only logs to CloudWatch) in `audit.py` | ✅ Correct |
| NOM-004 validation | Pydantic `model_validator` in `notas.py` | ✅ In-schema |
| X-Tenant-ID | Only in `testing` env in `tenant.py` | ✅ Correct |
  
### Rules I'll Enforce
  
1. No manual SQL audit logs — pgAudit handles it; the `AuditLog` model/route exists for the legacy UI query but new writes go through pgAudit
2. No DEK caching — `encrypt_field` / `decrypt_field` call KMS directly every time
3. No backend PDF — frontend uses `window.print()` 
4. NOM-004 validators in Pydantic — no external validation libs
5. X-Tenant-ID header → `testing` only, never `development` 
6. Clerk auth → JWT `publicMetadata` provee el `tenant_id`. La columna `clerk_id` en el modelo `Tenant` es exclusivamente para el mapeo en el onboarding.
7. Infraestructura → Aurora Serverless v2 es el estándar. Cualquier migración destructiva en Terraform DEBE usar el runbook de snapshots (`docs/runbooks/aurora_migration.md`).
7. /ponytail-review before suggesting any new service, cache, or middleware
  
### Notable Observation
  
The `tenant_key.py` model stores an `encrypted_dek` (envelope encryption key), but your `encryption.py` does direct KMS calls — the DEK is unused in the current encryption flow. This is consistent with your "no DEK cache" rule; the `TenantKey` table appears to be a legacy artifact or placeholder for future key rotation tracking.

---

### 🚀 Próximos Pasos Identificados (WIP)

Basado en el estado actual, las siguientes tareas críticas están pendientes:
1. **Flujo de Onboarding (NEW-02)**: Crear el endpoint `/api/v1/auth/onboarding` (o webhook) que enlace el `user_id` de Clerk con un nuevo `Tenant` (guardando el `clerk_id`), y asigne el `tenant_id` al `publicMetadata` del usuario en Clerk.
2. **Datos Médicos Reales (NOM-004)**: Actualizar el middleware `tenant.py` para que deje de inyectar "Médico Titular" y obtenga los datos reales del médico (desde la base de datos o desde el token Clerk de forma estricta) antes de firmar notas.
3. **CI/CD (CRIT-08)**: Configurar GitHub Actions para el despliegue automático del backend y Terraform.

---

Ready for your next task. What would you like to build or fix?