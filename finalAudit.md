# Reporte de Auditoría Final Pre-Beta de Seguridad y Cumplimiento Normativo - CloudMedRecord

He revisado minuciosamente el código base y verificado cada punto solicitado.

---

## 1. Firma ECDSA (NOM-024 §7.3.2.3)

✅ **Pass**

### Evidencia

- `backend/app/services/firma.py` define la forma canónica incluyendo `tenant_id`, `medico_nombre`, `medico_cedula` y `medico_especialidad`.
- En `backend/app/api/v1/notas.py` (líneas 257-271), el endpoint `POST /{nota_id}/firmar` obtiene la identidad del médico haciendo un `select(Tenant).where(Tenant.id == tenant_id)` directamente contra la base de datos (ignorando `request.state`).
- El modelo en `backend/app/models/tenant.py` define `cedula` con `nullable=False`, lo que hace imposible que se pueda firmar sin que exista una cédula válida en la base de datos.

---

## 2. Cifrado de columnas (NOM-024 + defense in depth)

✅ **Pass**

### Evidencia

- `backend/app/services/encryption.py` (líneas 48-54) llama directamente al método `kms.encrypt()`. No existe ningún diccionario en memoria que actúe como caché de DEKs.
- `backend/app/api/v1/pacientes.py` cifra y descifra `domicilio_cifrado` utilizando `encrypt_field` (línea 116) y `decrypt_field` (línea 158). Lo mismo ocurre en `expedientes.py`.
- `tenant_key.py` existe como modelo (*placeholder*), pero no interviene en `encryption.py`.

---

## 3. Auditoría (NOM-004)

✅ **Pass**

### Evidencia

- `backend/app/middleware/audit.py` (línea 88) únicamente registra la trazabilidad en un JSON estructurado vía `logger.info()`.
- En el mismo archivo (línea 90), un comentario aclara:

> "Todo el rastro legal se maneja ahora automáticamente a nivel de base de datos a través de la extensión pgaudit y AWS CloudTrail".

No hay rastros de sentencias `INSERT INTO audit_log` en la capa de aplicación.

---

## 4. Aislamiento Multi-Tenant (Seguridad)

✅ **Pass**

### Evidencia

- En `backend/app/db/session.py` (líneas 85-88), se inyecta el contexto ejecutando:

```sql
SELECT set_config('app.current_tenant', :tenant_id, true)
```

donde `true` indica que la variable solo vive durante el contexto transaccional (`SET LOCAL`).

- En `backend/app/middleware/tenant.py` (líneas 55-58), la asignación vía la cabecera `X-Tenant-ID` está estrictamente protegida por:

```python
if not tenant_id and settings.environment == "testing":
```

No opera ni en desarrollo ni en producción.

---

## 5. Autenticación y Onboarding (Clerk)

✅ **Pass**

### Evidencia

- `backend/app/core/security.py` contiene `_decode_clerk_jwt(token)` para validar las firmas RS256 contra las llaves públicas publicadas en el JWKS de Clerk.
- El modelo `backend/app/models/tenant.py` define:

```python
clerk_id: Mapped[str | None] = mapped_column(
    String(100),
    unique=True,
    index=True
)
```

- En `backend/app/api/v1/auth.py` (líneas 168-171) se verifica explícitamente si existe un inquilino para la misma cuenta con:

```python
select(Tenant).where(Tenant.clerk_id == user_id)
```

Si es así, retorna `already_onboarded` evitando creación de duplicados.

Además, se invoca la API de Clerk para persistir la información en `publicMetadata`.

---

## 6. Plan de Acceso (Beta)

❌ **Fail - Atomicidad Rota**

### Evidencia

- El sistema asigna `"basico"` por defecto en la BD y respeta el límite en el `POST` de `expedientes.py` (líneas 78-86). Sin embargo, la actualización atómica en el script falla.
- En `backend/scripts/upgrade_tenant.py` (líneas 33-35), el script hace un:

```python
await db.commit()
```

antes de intentar la llamada a la API de Clerk.

- Si la llamada HTTP a:

```text
https://api.clerk.com/v1/users/{tenant.clerk_id}/metadata
```

(línea 50) falla por problemas de red o cuota, la base de datos quedará permanentemente como `"pro"` pero el token de Clerk seguirá emitiendo `"basico"`.

### Minimal Fix

Mover el `await db.commit()` después de la confirmación de Clerk.

**Archivo:** `backend/scripts/upgrade_tenant.py`

```python
# Mover la línea 34 a la línea 63

# 1. Preparar Database (no hacer commit todavía)
tenant.plan = plan

# 2. Update Clerk Metadata
async with httpx.AsyncClient() as client:
    resp = await client.patch(...)
    resp.raise_for_status()

# 3. Solo si Clerk tiene éxito, aplicamos el commit a PostgreSQL
await db.commit()

logger.info(f"✅ Base de datos actualizada (plan={plan}).")
```

---

## 7. Generación de PDF

✅ **Pass**

### Evidencia

- Al revisar el árbol completo, particularmente `backend/app/services/`, el archivo `pdf.py` y cualquier dependencia de `fpdf2` ya no existen.
- No hay rastros de generación de PDF en backend; está totalmente delegado al frontend.

---

## 8. Validaciones NOM-004

✅ **Pass**

### Evidencia

- En `backend/app/api/v1/notas.py` (líneas 36-39), el esquema Pydantic `NotaCreate` incluye un:

```python
@model_validator(mode="after")
```

que exige implacablemente que cualquier nota marcada como `"evolucion"` traiga datos no vacíos en `signos_vitales` y en `diagnosticos`.

De lo contrario levanta un `ValueError`.

---

## 9. CI/CD y Terraform

✅ **Pass**

### Evidencia

En `.github/workflows/deploy.yml`:

- `plan-infrastructure-production` corre separadamente y guarda su output usando `actions/upload-artifact`.
- `apply-infrastructure-production` requiere:

```yaml
environment: production
```

(línea 226), lo que exige aprobación manual.

- La ejecución real:

```bash
terraform apply tfplan
```

(línea 261) no posee la bandera `-auto-approve`.

- La revisión a `docs/runbooks/aurora_migration.md` se promueve en la consola vía `echo` en el *step* de revisión del job de producción.

---

## 10. Documentación ADR

✅ **Pass**

### Evidencia

Existe el directorio:

```text
docs/architecture-decisions
```

y contiene los tres archivos marcados en la lista de verificación:

- `001-cifrado-columnas-vs-tde.md`
- `002-tenant-key-placeholder.md`
- `003-firma-ecdsa-obligatoria.md`

---

# Conclusión

Exceptuando la vulnerabilidad de atomicidad e inconsistencia de estado encontrada en el script `upgrade_tenant.py`, el sistema cumple exitosamente con los requisitos arquitectónicos y legales impuestos para liberar su estado a versión **Beta**.