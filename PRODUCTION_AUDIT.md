# 🔍 Auditoría de Producción — MedRecord SaaS

> **Autor:** Revisión técnica automatizada (Tech Lead)  
> **Fecha:** 10 de junio de 2026  
> **Alcance:** Seguridad, vulnerabilidades, arquitectura, cumplimiento normativo, prácticas de desarrollo  
> **Framework de referencia:** AWS Well-Architected Framework (6 pilares)

---

## Resumen Ejecutivo

MedRecord es un **Expediente Clínico Electrónico (ECE) multi-tenant** construido con FastAPI (Python 3.12) + React 19 (TypeScript), desplegado en AWS Lambda + Aurora Serverless v2. La base arquitectónica es **sólida para un MVP**, pero existen **8 hallazgos críticos** y **11 hallazgos importantes** que deben resolverse antes de recibir datos reales de pacientes en producción.

| Severidad | Cantidad | Bloqueante para Go-Live |
|-----------|----------|-------------------------|
| 🔴 Crítico | 8 | Sí |
| 🟡 Importante | 11 | Recomendado |
| 🔵 Mejora | 9 | No |

---

## Pilar 1: Seguridad (Security)

### 🔴 CRIT-01 — Secreto JWT hardcodeado en código fuente

**Archivos afectados:**
- `backend/app/core/security.py` (línea 30)
- `backend/app/api/v1/auth.py` (línea 39)

```python
LOCAL_JWT_SECRET = "medrecord-dev-secret-change-in-production"
JWT_SECRET = "medrecord-dev-secret-change-in-production"
```

**Riesgo:** El secreto de firma JWT está hardcodeado en texto plano. Cualquier persona con acceso al repositorio puede forjar tokens válidos. Aunque existe el guard `if settings.environment == "development"`, el secreto está en el historial de Git y viola el principio de no almacenar secretos en código.

**Remediación:**
1. Eliminar `LOCAL_JWT_SECRET` y `JWT_SECRET` del código fuente.
2. Para desarrollo: Generar un secreto aleatorio por sesión (`os.urandom(32)`) o leerlo de `.env.local`.
3. Para producción: Delegar 100% a Cognito (el backend solo valida el JWKS, nunca emite tokens).
4. Ejecutar `git filter-branch` o `git-filter-repo` para purgar el secreto del historial de Git.

---

### 🔴 CRIT-02 — El archivo `.env.local` está en el repositorio

**Archivo:** `backend/.env.local` (117 bytes, rastreado por Git)

Aunque `.gitignore` lista `.env.local`, el archivo **ya fue comiteado** (existe en el repo). Contiene la conexión directa a PostgreSQL con credenciales en texto plano.

**Remediación:**
1. `git rm --cached backend/.env.local`
2. Verificar que no haya otros `.env*` comiteados.
3. Agregar un pre-commit hook que rechace archivos `.env*`.

---

### 🔴 CRIT-03 — Tokens almacenados en `localStorage` (XSS → robo de sesión)

**Archivo:** `frontend/src/services/auth.ts` (líneas 77-79)

```typescript
localStorage.setItem(TOKEN_KEY, data.access_token);
localStorage.setItem(USER_KEY, JSON.stringify(_extractUser(data)));
```

**Riesgo:** `localStorage` es accesible por cualquier JavaScript en la página. Si existe una vulnerabilidad XSS (incluso vía un paquete npm comprometido), un atacante puede exfiltrar el token JWT y suplantar al médico.

**Remediación:**
- **Fase 1 (Cognito):** Usar `@aws-amplify/auth` que almacena tokens en un lugar más seguro y maneja refresh automáticamente.
- **Alternativa (sin Cognito):** Mover el token a una cookie `HttpOnly; Secure; SameSite=Strict` emitida por el backend. El frontend nunca ve el token.

---

### 🔴 CRIT-04 — CORS acepta `allow_headers=["*"]`

**Archivo:** `backend/app/main.py` (línea 44)

```python
allow_headers=["*"],
```

**Riesgo:** Permite que cualquier header sea enviado en CORS preflight, lo que puede facilitar ataques de tipo CSRF o relay de tokens.

**Remediación:**
```python
allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
```

---

### 🔴 CRIT-05 — Falta rate limiting en endpoints de autenticación

**Archivos:** `backend/app/api/v1/auth.py` — `/login` y `/register`

No existe throttling a nivel de aplicación. El WAF de Terraform tiene un rate limit global (1000/5min/IP), pero:
- No protege contra ataques de credential stuffing distribuidos.
- No hay penalización exponencial tras intentos fallidos.
- No hay CAPTCHA o mecanismo anti-bot.

**Remediación:**
1. Implementar un decorador de rate limiting por IP + email (ej: `slowapi` o Redis counter).
2. Bloquear cuenta temporalmente tras 5 intentos fallidos consecutivos.
3. Cognito en producción resuelve esto nativamente con Advanced Security.

---

### 🔴 CRIT-06 — Bypass de autenticación X-Tenant-ID en modo desarrollo

**Archivo:** `backend/app/middleware/tenant.py` (líneas 56-73)

```python
if request.headers.get("X-Tenant-ID"):
    if settings.environment != "development":
        return JSONResponse(status_code=403, ...)
    # Dev bypass allows unauthenticated access
```

**Riesgo:** Si `ENVIRONMENT` no se configura correctamente al desplegar (valor por defecto es `"development"`), **cualquiera** puede acceder sin autenticación enviando el header `X-Tenant-ID`.

**Remediación:**
1. Cambiar el default de `environment` en `config.py` a `"production"` (fail-closed).
2. Eliminar completamente el bypass de `X-Tenant-ID` del código de producción. Puede vivir solo en tests.
3. Agregar un test que verifique que `X-Tenant-ID` es rechazado cuando `ENVIRONMENT != "development"`.

---

### 🟡 IMP-01 — No hay validación de UUID en path parameters

**Archivos:** Todos los endpoints que reciben `paciente_id`, `nota_id`, `expediente_id`.

```python
@router.get("/{paciente_id}")
async def get_paciente(paciente_id: str, ...):
```

**Riesgo:** Acepta strings arbitrarias que se pasan directamente a la query SQL. Aunque SQLAlchemy usa parámetros preparados (evitando SQLi), la falta de validación de formato puede causar errores inesperados o permitir enumeration attacks.

**Remediación:**
```python
from uuid import UUID
@router.get("/{paciente_id}")
async def get_paciente(paciente_id: UUID, ...):
```

---

### 🟡 IMP-02 — Falta Content Security Policy (CSP) y headers de seguridad

El frontend no envía headers HTTP de seguridad:
- `Content-Security-Policy`
- `Strict-Transport-Security` (HSTS)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

**Remediación:** Agregar estos headers en CloudFront (para el SPA) y en la respuesta de API Gateway/Lambda.

---

### 🟡 IMP-03 — La expiración del JWT es de 24 horas

**Archivo:** `backend/app/api/v1/auth.py` (línea 41)

```python
JWT_EXPIRY_HOURS = 24
```

Para una aplicación que maneja datos de salud, 24 horas es excesivo. La sesión puede ser secuestrada durante horas.

**Remediación:**
- Access token: 15 minutos (ya configurado en Cognito TF: `access_token_validity = 15`).
- Refresh token: 7 días.
- Implementar refresh silencioso en el frontend.

---

### 🟡 IMP-04 — No hay MFA en el entorno de desarrollo local

El código actual usa bcrypt + JWT local. El Cognito configurado en Terraform sí tiene `mfa_configuration = "ON"`, pero el flujo local lo ignora completamente. Si algún piloto usa el modo local, no tendrá MFA.

**Remediación:** Documentar explícitamente que la autenticación local es SOLO para desarrollo y que el despliegue de producción DEBE usar Cognito con MFA.

---

## Pilar 2: Fiabilidad (Reliability)

### 🔴 CRIT-07 — No hay mecanismo de retry/offline para el frontend

**Archivo:** `PRODUCTION_DEBT.md` (punto 3)

Si el doctor pierde conexión a internet durante una consulta, **la nota médica se pierde**. No hay:
- Service Worker / PWA
- Guardado local (IndexedDB)
- Cola de sincronización
- Indicador de estado de conexión

**Remediación (Fase 1 simplificada):**
1. Guardar borradores de notas en `localStorage` con autosave cada 30 segundos.
2. Mostrar un banner claro cuando no hay conexión.
3. Reintentar automáticamente al recuperar red.

---

### 🟡 IMP-05 — Single-AZ NAT Gateway

**Archivo:** `terraform/modules/networking/main.tf` (línea 83)

Solo hay un NAT Gateway en una AZ. Si esa AZ falla, Lambda pierde acceso a internet (KMS, Secrets Manager, etc.).

**Remediación para 20 doctores:** Aceptable en MVP. Documentar como deuda técnica con SLA claro. El RPO/RTO es tolerable para este volumen.

---

### 🟡 IMP-06 — `BaseHTTPMiddleware` tiene problemas conocidos con asyncio

**Archivos:** `backend/app/middleware/audit.py`, `backend/app/middleware/tenant.py`

Starlette's `BaseHTTPMiddleware` ejecuta el handler en un thread separado y tiene bugs conocidos con `request.state` y streaming. Esto puede causar errores intermitentes bajo carga.

**Remediación:** Migrar a Pure ASGI Middleware (raw ASGI) o usar FastAPI Dependencies.

---

## Pilar 3: Eficiencia de Rendimiento (Performance Efficiency)

### 🟡 IMP-07 — No hay paginación cursor-based ni conteo total

Los endpoints `list_pacientes`, `list_notas`, `list_expedientes` usan offset/limit sin devolver el total.

**Impacto:** Funcional para 20 doctores, pero degrada con el tiempo.

**Remediación:** Agregar `total_count` en la respuesta y considerar cursor-based pagination para listas grandes.

---

### 🟡 IMP-08 — Lambda Cold Start con 512 MB RAM

**Archivo:** `terraform/modules/compute/main.tf` (línea 144)

`memory_size = 512` para una Lambda que carga FastAPI + SQLAlchemy + cryptography. Cold starts pueden ser lentos (3-5 segundos).

**Remediación:**
1. Subir a `1024 MB` (mejora proporcionalmente el CPU asignado, reduciendo cold start a ~1.5s).
2. Habilitar Provisioned Concurrency con 2 instancias en horario laboral (9-21h MX).

---

## Pilar 4: Excelencia Operacional (Operational Excellence)

### 🔴 CRIT-08 — No hay pipeline de CD (solo CI)

**Archivo:** `.github/workflows/ci.yml`

El pipeline actual solo ejecuta lint, tests, y build. **No hay despliegue automatizado**. Sin CD:
- Los despliegues son manuales y propensos a error.
- No hay rollback automatizado.
- No hay aprobación de cambios antes de ir a producción.

**Remediación:**
1. Crear un workflow `deploy.yml` con stages: `plan → apply (staging) → smoke test → apply (prod)`.
2. Usar GitHub Environments con `required_reviewers`.
3. `terraform plan` como comentario en PRs.

---

### 🟡 IMP-09 — No hay structured logging

Las líneas de log en el backend usan `logger.info()` con strings formateados, no JSON estructurado. En CloudWatch esto dificulta el análisis y alertado.

**Remediación:** Configurar `structlog` o `python-json-logger` con campos estándar: `timestamp`, `level`, `tenant_id`, `request_id`, `user_id`.

---

### 🟡 IMP-10 — No hay alerta cuando falla la persistencia de audit

**Archivo:** `backend/app/middleware/audit.py` (líneas 152-159)

```python
except Exception as exc:
    logger.error("CRITICAL: Failed to persist audit log to database...")
```

El fallo se registra en CloudWatch pero **no dispara ninguna alarma SNS**. Para un sistema donde el audit trail es legalmente obligatorio, esto es inaceptable.

**Remediación:**
1. Crear un CloudWatch Metric Filter que detecte `"CRITICAL: Failed to persist audit"`.
2. Vincular ese filtro a una alarma SNS con notificación inmediata.

---

### 🔵 MEJORA-01 — Terraform environments/dev está vacío de `main.tf`

No existe un archivo `main.tf` en `terraform/environments/dev/` que orqueste los módulos. Esto indica que los módulos nunca han sido aplicados.

---

## Pilar 5: Optimización de Costos (Cost Optimization)

### 🔵 MEJORA-02 — Aurora Serverless min_capacity 0.5 ACU

```hcl
min_capacity = 0.5 # $43/month
```

Para 20 doctores con uso intermitente, esto es adecuado. **No se requiere cambio.** El auto-scale a 4 ACU cubre picos.

---

### 🔵 MEJORA-03 — NAT Gateway ($32/mes) + transferencia

Un NAT Gateway cuesta ~$32/mes fijo más cargos de transferencia. Para 20 doctores con bajo tráfico, considerar usar **VPC Endpoints** para S3, KMS, Secrets Manager, y CloudWatch. Esto eliminaría la necesidad de NAT Gateway y ahorraría ~$30/mes.

---

## Pilar 6: Sostenibilidad (Sustainability)

### 🔵 MEJORA-04 — Sin métricas de observabilidad de negocio

No hay dashboards que muestren:
- Notas creadas por doctor por día.
- Pacientes activos por tenant.
- Tasa de firma digital (notas firmadas vs borradores).

Estas métricas son útiles para validar el product-market fit.

---

## Análisis de Cumplimiento Normativo

### NOM-004-SSA3-2012 (Expediente Clínico)

| Requisito | Estado | Observación |
|-----------|--------|-------------|
| Datos de identificación (§5.3) | ✅ | `nombre_completo`, `sexo`, `fecha_nacimiento` obligatorios. |
| Historia clínica (§5.4) | ✅ | `antecedentes_cifrado` con AES-256-GCM. |
| Notas médicas con autoría (§5.8) | ✅ | Snapshot de `medico_nombre`, `medico_cedula`, `firmado_en`. |
| Conservación 5 años (§5.14) | ✅ | Soft delete + S3 lifecycle 1825 días + Object Lock. |
| Inmutabilidad post-firma (§6.2) | ✅ | `es_editable = false` + ECDSA P-256 signature. |
| Validadores NOM-004 incompletos | ⚠️ | Solo `evolucion` e `interconsulta` tienen validador. Faltan: `ingreso`, `egreso`, `quirurgica`, etc. |

### NOM-024-SSA3-2012 (SIRES)

| Requisito | Estado | Observación |
|-----------|--------|-------------|
| Cifrado en reposo | ✅ | KMS CMK + Aurora encrypted + S3 SSE-KMS. |
| Cifrado en tránsito | ⚠️ | TLS implícito en API Gateway, pero falta forzar TLS 1.2+ en RDS Proxy (ya configurado en TF). |
| Firma electrónica | ✅ | ECDSA P-256 vía KMS. Verificación de integridad funcional. |
| Audit trail inmutable | ⚠️ | El trigger de BD para prevenir UPDATE/DELETE en `audit_log` está **referenciado en docs pero no implementado en código SQL**. |
| RBAC | ⚠️ | Solo existe aislamiento por tenant. No hay roles internos (Médico vs Asistente vs Admin). |

### LFPDPPP (Datos Personales)

| Requisito | Estado | Observación |
|-----------|--------|-------------|
| Aviso de privacidad | ✅ | Template completo en `docs/legal/aviso_privacidad_template.md`. |
| Consentimiento expreso | ⚠️ | El endpoint `/audit/consentimiento` solo registra un evento. No persiste el consentimiento en una tabla dedicada ni genera un documento firmado. |
| Derechos ARCO | ⚠️ | No existe endpoint de exportación de datos ni flujo de solicitud ARCO. |
| Notificación de brecha | ✅ | Protocolo documentado en `docs/legal/breach_protocol.md`. |

---

## Análisis de Seguridad — Frontend

### 🟡 IMP-11 — Falta sanitización de inputs en componentes React

Los formularios de pacientes y notas confían en la validación del backend sin sanitizar en el frontend. Aunque React escapa por defecto en JSX, los datos que se pasan a `dangerouslySetInnerHTML` o se inyectan en URLs podrían ser vectores de XSS.

**Remediación:** Agregar validación y sanitización en los formularios del frontend (ya que también mejora la UX).

---

## Análisis de Dependencias

### 🔵 MEJORA-05 — Falta auditoría de dependencias automatizada

No hay `npm audit` ni `pip-audit` en el pipeline CI. Las dependencias de seguridad (`cryptography`, `PyJWT`, `bcrypt`) deben monitorearse continuamente.

**Remediación:** Agregar jobs de `npm audit --audit-level=high` y `pip-audit` en el CI pipeline. Habilitar Dependabot en el repositorio.

---

### 🔵 MEJORA-06 — Falta pinning estricto de versiones Python

**Archivo:** `backend/pyproject.toml`

Las dependencias usan rangos (`>=0.110`, `>=2.0`). Esto puede causar builds no reproducibles.

**Remediación:** Generar `requirements.lock` o usar `pip-compile` para pinear versiones exactas en producción.

---

## Análisis del Diseño de Base de Datos

### 🔵 MEJORA-07 — El campo `password_hash` vive en la tabla `tenants`

En producción con Cognito, este campo es innecesario y supone un riesgo si la base de datos es comprometida.

**Remediación:** Después de migrar a Cognito, eliminar la columna `password_hash` y los endpoints de autenticación local.

---

### 🔵 MEJORA-08 — Falta índice en `audit_log.timestamp`

El audit_log crecerá rápidamente. Aunque hay un `index=True` en el modelo, verificar que también existan índices parciales para queries frecuentes (por `tenant_id + timestamp`).

---

### 🔵 MEJORA-09 — Trigger de inmutabilidad del audit_log no implementado

La documentación menciona que "la tabla prohíbe UPDATE y DELETE" mediante un trigger, pero **no existe ningún SQL de trigger** en el repositorio. El `rls_init.sql` solo revoca DELETE del rol `medrecord_app`, pero no cubre UPDATE (el REVOKE solo revoca DELETE, no UPDATE).

**Remediación:**
```sql
CREATE OR REPLACE FUNCTION prevent_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'La tabla audit_log es inmutable. No se permiten UPDATE ni DELETE.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_mutation();
```

---

## Resumen de Acciones Bloqueantes (Go/No-Go)

| # | Hallazgo | Esfuerzo Est. | Prioridad |
|---|----------|--------------|-----------|
| CRIT-01 | JWT secret hardcodeado | 2h | P0 |
| CRIT-02 | `.env.local` comiteado | 30min | P0 |
| CRIT-03 | Tokens en localStorage | 4h (con Cognito) | P0 |
| CRIT-04 | CORS `allow_headers=*` | 15min | P0 |
| CRIT-05 | Sin rate limiting en auth | 3h | P0 |
| CRIT-06 | Default `environment=development` | 1h | P0 |
| CRIT-07 | Sin autosave/offline | 8h | P1 |
| CRIT-08 | Sin pipeline CD | 8h | P0 |
| IMP-09→11 | Validaciones/headers | 4h total | P1 |

**Estimación total para Go-Live seguro: ~30-35 horas de trabajo.**

---

> *Este documento debe ser revisado y actualizado tras cada sprint pre-producción. Los hallazgos etiquetados como 🔴 son bloqueantes para recibir datos reales de pacientes.*
