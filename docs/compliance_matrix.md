# Matriz viva de cumplimiento normativo

> Sustituye la matriz anterior de estado binario "Cumple ✅". Sigue el §14.1 del
> `ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2.md`: cada requisito registra norma/numeral,
> interpretación, responsable, control técnico, procedimiento, prueba, evidencia,
> fecha, versión y riesgo residual, con un estado honesto y no autoproclamado.
>
> **Este documento no es un dictamen jurídico.** No se publica "cumple NOM-004/NOM-024"
> por autoevaluación; el producto se describe como **"diseñado para apoyar el
> cumplimiento"** hasta contar con revisión o evaluación formal aplicable (§14 del roadmap).

**Versión:** 2.0 · **Fecha de revisión:** 2026-07-14 · **Próxima revisión:** trimestral
o extraordinaria si el DOF publica cambios.

## Estados válidos

| Estado | Significado |
|---|---|
| `no evaluado` | No se ha analizado ni implementado control alguno. |
| `parcial` | Existe control pero con brechas conocidas o cobertura incompleta. |
| `implementado` | Control presente y verificado **en código/infra** por el equipo (no auditoría externa). |
| `verificado independiente` | Confirmado por auditoría/pentest externo. **Ninguno lo tiene aún** (pendiente de Fase 9). |

> Corrección de datos respecto a la matriz anterior: la base es **RDS PostgreSQL**
> (`aws_db_instance`, no Aurora); la identidad es **Clerk** (JWT, no Cognito); la
> auditoría es **middleware a nivel request** (`AuditMiddleware`, no triggers de fila
> con `datos_antes/datos_despues`). El aislamiento multi-tenant se deriva del **JWT de
> Clerk**, no de un header `X-Tenant-ID` de cliente (ese header es solo para pruebas).

---

## Resumen — NOM-004-SSA3-2012 (del expediente clínico)

| Numeral | Control técnico | Estado | Riesgo residual |
|---|---|---|---|
| 5.3 Identificación del paciente | Modelo `Paciente` exige `nombre_completo`, `sexo`, `fecha_nacimiento`; validación en frontend/schema | implementado | Segundo identificador / banner de identidad pendiente (Fase 12) |
| 5.4 Historia clínica completa | Antecedentes en JSONB cifrado (KMS envelope) en `expedientes` | parcial | Historia longitudinal estructurada (alergias/problemas/medicamentos) pendiente (Fase 12) |
| 5.8 Nota con fecha, hora, nombre y firma | `notas` con timestamp, firma KMS ECDSA, snapshot inmutable de `medico_nombre/cedula/especialidad` | implementado | Snapshot vive en `tenants` (una credencial); modelo `medicos` multi-credencial pendiente (Fase 1) |
| 5.10 Corrección / addenda | Nota firmada inmutable por trigger; corrección solo como nota nueva | parcial | Flujo de addenda formal con referencia al original pendiente (Fase 12) |
| 5.14 Conservación (≥5 años) | `REVOKE DELETE` + triggers `prevent_notas/expedientes_deletion`; `activo` soft-delete | parcial | Retención calculada desde el último acto médico y lifecycle S3→Glacier no verificados |

## Resumen — NOM-024-SSA3-2012 (sistemas de registro e intercambio)

| Tema | Control técnico | Estado | Riesgo residual |
|---|---|---|---|
| Cifrado en reposo/tránsito | TLS en tránsito; KMS envelope (CMK+DEK) en RDS PostgreSQL y S3 (SSE-KMS) | implementado | Alcance de cifrado por columna vs. instancia pendiente de documentar por dato |
| Firma electrónica | `firma.py` firma con KMS asimétrica `ECDSA_SHA_256` sobre hash SHA-256 del contenido canónico; token de verificación pública | implementado | Firma electrónica avanzada (e.firma/PSC) fuera de alcance actual |
| Trazabilidad / bitácora | `AuditMiddleware` registra request (método, ruta, status, duración, tenant); `audit_log` append-only con trigger de inmutabilidad (UPDATE/DELETE bloqueados) | implementado | Bitácora a nivel campo (antes/después) no implementada; es a nivel request/operación |
| Control de acceso | Autenticación JWT asimétrico (Clerk); aislamiento multi-tenant por RLS en PostgreSQL derivado del JWT | parcial | Roles internos (propietario/médico/recepción) pendientes (Fase 14); validación completa de claims Clerk pendiente (Fase 9) |
| Integridad | Verificación pública recalcula hash y valida firma matemáticamente | implementado | — |

---

## Detalle por requisito (§14.1)

### NOM-004 §5.8 — Nota con fecha, hora, nombre y firma
- **Interpretación:** toda nota médica debe registrar fecha/hora, identidad y firma del médico responsable, y ser inalterable tras firmarse.
- **Responsable:** médico responsable (contenido) · CloudMedRecord encargado (control técnico).
- **Control técnico:** `notas` con `firmado_en`, firma KMS ECDSA (`firma_digital`, `firma_hash_contenido`, `firma_kms_key_id`), snapshot `medico_nombre/cedula/especialidad`; trigger `notas_signed_immutable` bloquea UPDATE cuando `es_editable=false`.
- **Procedimiento operativo:** el médico firma desde la UI; el backend persiste firma + token de verificación en la misma transacción.
- **Prueba:** `tests/integration/test_nota_signing_immutability_trigger.py` (corre contra el trigger real de Alembic en el job de migración, `@pytest.mark.migration_schema`).
- **Evidencia:** migración `a1b2c3d4e5f6`; regresión verde en CI.
- **Estado:** implementado · **Riesgo residual:** la credencial de firma vive en `tenants` (una sola); el modelo `medicos` multi-credencial (Fase 1) mejora la fidelidad NOM del firmante.

### NOM-004 §5.14 — Conservación mínima
- **Interpretación:** el expediente debe conservarse al menos 5 años a partir del último acto médico.
- **Responsable:** CloudMedRecord encargado.
- **Control técnico:** `REVOKE DELETE` sobre tablas clínicas para `medrecord_app`; triggers `prevent_notas_deletion` / `prevent_expedientes_deletion` bloquean DELETE incluso a superuser; `pacientes.activo` para baja lógica.
- **Procedimiento operativo:** no existen endpoints de hard-delete clínico; las bajas son lógicas.
- **Prueba:** `scripts/verify_rls.py` y el verificador estructural `verify_rls` (registro `scripts/verify_registry.py`).
- **Evidencia:** migraciones `a1b2c3d4e5f6`, `f1e2d3c4b5a6`.
- **Estado:** parcial · **Riesgo residual:** la conservación calculada **desde el último acto médico** y el lifecycle S3→Glacier IR (1825 días) no están verificados como política computada; separar retención legal vs. recuperación (Fase 10).

### NOM-024 — Trazabilidad / bitácora inalterable
- **Interpretación:** el sistema debe mantener una bitácora inalterable de accesos y operaciones.
- **Responsable:** CloudMedRecord encargado.
- **Control técnico:** `AuditMiddleware` inserta una entrada por request (método, ruta, status, duración, tenant pseudonimizado); `audit_log` es append-only y el trigger `audit_log_immutable` bloquea UPDATE/DELETE.
- **Procedimiento operativo:** automático en cada request; sin PHI en la bitácora.
- **Prueba:** `tests/integration/test_audit.py`.
- **Evidencia:** migraciones `a1b2c3d4e5f6`, `e3c4d5f6a7b8`.
- **Estado:** implementado · **Riesgo residual:** es bitácora a nivel request/operación, no a nivel campo (antes/después). Exportación de bitácora para auditoría pendiente (§14.3).

### NOM-024 — Control de acceso y aislamiento multi-tenant
- **Interpretación:** acceso por roles/privilegios y aislamiento estricto entre responsables.
- **Responsable:** CloudMedRecord encargado.
- **Control técnico:** autenticación JWT asimétrico (Clerk); RLS en PostgreSQL (`FORCE` + política `tenant_isolation_*`) con `tenant_id` derivado del JWT; la app se conecta como rol no-superusuario `medrecord_app`.
- **Procedimiento operativo:** cada transacción hace `SET LOCAL ROLE medrecord_app` + `set_config('app.current_tenant', ...)`.
- **Prueba:** `scripts/verify_rls.py` (job de migración CI) + `verify_rls` estructural en prod (read-only).
- **Evidencia:** migración `a1b2c3d4e5f6`; job `migration-check` en `.github/workflows/ci.yml`.
- **Estado:** parcial · **Riesgo residual:** el drift de `FORCE ROW LEVEL SECURITY` en `consentimientos` y `recetas` fue corregido (migración `45fd65e2a92f`; guardián de regresión en `test_verify_rls_structure.py`). Pendientes: roles internos (Fase 14) y validación completa de claims Clerk (Fase 9).

---

## Privacidad y datos personales (LFPDPPP vigente) — inventario de brechas

El roadmap §14.2 exige controles de privacidad que hoy **no** están implementados. Se listan
honestamente para no dar impresión de cobertura inexistente.

| Requisito | Estado | Nota |
|---|---|---|
| Aviso de privacidad versionado + evidencia de aceptación | parcial | Existe aceptación de términos (`terms_accepted_at/version` en `tenants`); falta aviso de privacidad como documento versionado con registro del texto aceptado por el paciente |
| Inventario de datos, finalidades y transferencias | no evaluado | Pendiente de elaborar |
| Contrato responsable–encargado (AWS, Clerk, etc.) | no evaluado | Jurídico |
| Flujo ARCO (acceso, rectificación, cancelación, oposición) | no evaluado | Fase 15 (exportación) es prerequisito técnico parcial |
| Retención diferenciada (logs/borradores/respaldos/finales) | no evaluado | Ligado a NOM-004 §5.14 |
| Gestión de incidentes/vulneración | no evaluado | Fase 9/10 |
| Prohibición de PHI en analítica/IA sin base jurídica | parcial | Telemetría diseñada sin PHI (§19), sin control formal aún |

---

## Brechas abiertas priorizadas

1. ~~**FORCE RLS en `consentimientos` y `recetas`**~~ — corregido (migración `45fd65e2a92f`); `test_verify_rls_structure.py` es ahora el guardián de regresión.
2. **Modelo `medicos` multi-credencial (Fase 1)** — mejora fidelidad del firmante NOM-004.
3. **Validación completa de claims Clerk + MFA/reauth (Fase 9)** — bloqueo de venta.
4. **Retención calculada desde el último acto médico (Fase 10)** — separar retención legal de recuperación.
5. **Controles LFPDPPP (aviso de privacidad, ARCO, contratos)** — requieren revisión jurídica.

> Las fuentes oficiales (DOF, Cámara de Diputados) prevalecen sobre este documento. Ante
> cualquier cambio normativo se actualiza primero esta matriz y luego la implementación (§21).
