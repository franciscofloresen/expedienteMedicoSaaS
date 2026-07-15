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
| 5.8 Nota con fecha, hora, nombre y firma | `notas` con timestamp, firma KMS ECDSA, snapshot inmutable de `medico_nombre/cedula/especialidad`; identidad del firmante resuelta por un adaptador único desde `medicos`/`medico_credenciales` (Fase 1) con fallback a `tenants` | implementado | El retiro de los campos de firma en `tenants` es la última migración (Fase 8); múltiples credenciales por documento aún no seleccionables en UI |
| 5.10 Corrección / addenda | Nota firmada inmutable por trigger; corrección solo como nota nueva | parcial | Flujo de addenda formal con referencia al original pendiente (Fase 12) |
| 5.14 Conservación (≥5 años) | `REVOKE DELETE` + triggers `prevent_*_deletion` en tablas clínicas; `activo` soft-delete; **respaldo restaurable a 5 años**: AWS Backup mensual (1825 d) en vault con Vault Lock COMPLIANCE (WORM) + PITR 35 d | implementado | Ensayo de restore superado 2026-07-15 (RTO ~17 min); pendiente: purga computada desde el último acto médico y checks de contenido del ensayo (Fase 10) |

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
- **Control técnico:** `notas` con `firmado_en`, firma KMS ECDSA (`firma_digital`, `firma_hash_contenido`, `firma_kms_key_id`), snapshot `medico_nombre/cedula/especialidad`; trigger `notas_signed_immutable` bloquea UPDATE cuando `es_editable=false`. La identidad estampada la resuelve el adaptador único `get_credencial_para_firma` desde la credencial predeterminada activa de `medicos`/`medico_credenciales` (Fase 1), con fallback a los campos de `tenants` durante la transición; `tenants.cedula` se mantiene sincronizada con la credencial predeterminada.
- **Procedimiento operativo:** el médico firma desde la UI; el backend persiste firma + token de verificación en la misma transacción. Onboarding crea médico + credencial predeterminada en la misma transacción (doble escritura); `update_profile` sincroniza la credencial al editar cédula/especialidad.
- **Prueba:** `tests/integration/test_nota_signing_immutability_trigger.py` y `tests/integration/test_medicos_credenciales.py` (adaptador, RLS, unicidades, protección de borrado, provisión/sincronización), ambos `@pytest.mark.migration_schema` contra el esquema migrado real.
- **Evidencia:** migraciones `a1b2c3d4e5f6` (trigger), `efb69dbb7dfb` (medicos/credenciales + backfill); regresión verde en CI.
- **Estado:** implementado · **Riesgo residual:** el retiro de los campos de firma en `tenants` es la última migración (Fase 8); selección de credencial por documento en UI pendiente.

### NOM-004 §5.14 — Conservación mínima
- **Interpretación:** el expediente debe conservarse al menos 5 años a partir del último acto médico.
- **Responsable:** CloudMedRecord encargado.
- **Control técnico:** `REVOKE DELETE` sobre tablas clínicas para `medrecord_app`; triggers `prevent_{pacientes,notas,expedientes,recetas,consentimientos,medicos,medico_credenciales}_deletion` bloquean DELETE incluso a owner/superuser; `pacientes.activo` / `medicos.activo` / `medico_credenciales.activa` para baja lógica. Los tokens de verificación (integridad de firmas) también tienen `REVOKE DELETE` de la app. Una credencial usada en un documento firmado se **desactiva, nunca se borra**.
- **Respaldo y recuperación (durabilidad):** AWS Backup con plan mensual retenido 1825 días en el vault `medrecord-legal-5yr-prod` con **Vault Lock en modo compliance (WORM)** — snapshots RDS reales, restaurables, cifrados KMS, inmutables incluso para root (lock permanente 2026-07-18). Complementa el PITR de 35 días de RDS (0–35 d = PITR; 35 d–5 años = archivo mensual). Notificaciones SNS a `medrecord-alarms-prod` en `BACKUP_JOB_FAILED`/`EXPIRED`/`RESTORE_JOB_FAILED`. Reemplaza el pipeline Parquet muerto (no restaurable) que se decomisionó.
- **Procedimiento operativo:** no existen endpoints de hard-delete clínico; las bajas son lógicas. Excepción controlada: `release_cedula.py` puede liberar la cédula de un tenant **huérfano** (sin datos clínicos) deshabilitando transaccionalmente los triggers de `medicos`/`medico_credenciales` para retirar solo la identidad backfilled no usada; si el tenant tiene datos clínicos la FK aborta el borrado y el rollback restaura triggers y filas.
- **Prueba:** verificadores estructurales `verify_rls` y `verify_medicos` (`scripts/verify_registry.py`) con check de delete-protection por tabla; guardianes de regresión en `test_verify_rls_structure.py` y `test_medicos_credenciales.py`. Respaldo: verificador `backups` (recovery point COMPLETED < 40 d en el vault, `test_verify_backups.py`) y **ensayo de restore real** ejecutado (§5.2 del runbook).
- **Evidencia:** migraciones `a1b2c3d4e5f6`, `f1e2d3c4b5a6`, `5eb13dab23be`, `8d3d86bc8393`, `efb69dbb7dfb`. Respaldo a 5 años: PR #117 (`terraform/modules/database/backup.tf`); ensayo de restore 2026-07-15 — backup job `e45d9f3c…` y restore job `731d771e…` COMPLETED, **RTO ~17 min / RPO ~0** (`docs/runbooks/backup_retention_5years.md` §5.2).
- **Estado:** implementado · **Riesgo residual:** la **purga computada desde el último acto médico** (política de retención legal, distinta de la conservación/respaldo ya cubiertos) queda para Fase 10; los checks de contenido del ensayo de restore (conteos vs. prod, hash de nota firmada) se difirieron al primer ensayo trimestral por falta de ruta de red al instante de restore.

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
