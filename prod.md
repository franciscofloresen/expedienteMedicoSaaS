# 📊 Análisis del Proyecto: Estado Actual

## ✅ Completado

- **Autenticación Delegada:** Migración completa a Clerk completada (tokens manejados por Clerk, eliminación de almacenamiento en `localStorage`, protección contra fuerza bruta cubierta).
- **Seguridad (Capa 1):** Eliminación de secretos JWT hardcodeados en el código.
- **Cumplimiento NOM-004/024:** Trigger de inmutabilidad en PostgreSQL para la tabla `audit_log` implementado y funcionando (nadie puede borrar o alterar un registro de auditoría).
- **Hardening de API:** Validación estricta de UUID en los parámetros de ruta, cabeceras de seguridad añadidas en middleware, y lista blanca estricta de orígenes en CORS.
- **Limpieza de Dependencias:** Gran parte de `fix.md` ya se ejecutó (se borraron dependencias innecesarias de React como `framer-motion`, `axios`, `date-fns-tz` y de Python como `slowapi` y `email-validator`).

---

## ⏳ Qué falta (Prioridad Alta)

- **Vulnerabilidad Crítica (NEW-01):** El middleware `tenant.py` tiene un bypass peligroso que usa la cabecera `X-Tenant-ID` incluso en peticiones autenticadas, permitiendo que un usuario válido acceda a los pacientes de otra clínica si conoce el UUID. Esto bloquea el paso a producción.
- **Flujo de Onboarding (NEW-02):** No hay tabla o mapeo que asocie el `user_id` de Clerk con un `tenant_id` en la base de datos.
- **Limpieza Post-Migración (MEJORA-07):** [COMPLETADO] La columna `password_hash` y la dependencia `bcrypt` fueron eliminadas exitosamente.
- **Bug de Importación:** En `backend/app/api/v1/notas.py`, todavía existe un `import validate_nom004` hacia `nom_validator.py` (el cual ya fue eliminado). Esto romperá la aplicación en ejecución.
- **Infraestructura CI/CD (CRIT-08):** Falta configurar los GitHub Actions para el despliegue a los entornos de AWS.
- **Datos Médicos en Firma:** `tenant.py` inyecta temporalmente `"Médico Titular"` o `"ND"` en los campos de `medico_nombre` y `medico_cedula`. Deben ser extraídos de la base de datos o de los metadatos de Clerk para cumplir fielmente la NOM-004.

---

## ✂️ Ponytail Audit (Over-engineering)

| Acción | Descripción | Archivo |
|--------|-------------|---------|
| 🔁 Nativo | Lógica de caché/rotación DEK de envelope encryption. AWS RDS TDE nativo con KMS y Postgres RLS manejan este aislamiento sin código de aplicación. | `backend/app/services/encryption.py` |
| 🔁 Nativo | Serialización canónica personalizada y lógica de firma ECDSA con KMS para notas. Los triggers de inmutabilidad de fila (¡ya implementados!) + AWS CloudTrail + RDS pgaudit son suficientes para trazas de auditoría NOM-004/024 sin criptografía manual. | `backend/app/services/firma.py` |
| 🔁 Nativo | Inserciones SQL directas vía sesiones async dedicadas en el middleware de auditoría. Usar la extensión pgaudit de PostgreSQL o triggers nativos en lugar de reinventar el ledger de auditoría en Python. | `backend/app/middleware/audit.py` |
| 🔁 Nativo | Generación de PDF en servidor usando `fpdf2`. Generar PDF vía `window.print()` del navegador y CSS `@media print`. | `backend/app/services/pdf.py` |
| 🗑️ Eliminar | Código muerto: import de `validate_nom004`. El archivo `nom_validator.py` fue eliminado, pero `notas.py` sigue importándolo y llamándolo. | `backend/app/api/v1/notas.py` |
| 🗑️ Eliminar | Columna `password_hash` sin uso y paquete `bcrypt` sobrantes de la migración a autenticación con Clerk. | `backend/app/models/tenant.py` |

**Líneas eliminables:** ~750 líneas

**Dependencias eliminables:** `cryptography`, `fpdf2`, `bcrypt`