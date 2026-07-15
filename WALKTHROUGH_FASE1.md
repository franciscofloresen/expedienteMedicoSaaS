# Walkthrough — Fase 1: Médicos y credenciales

> Narrativa de lo que se construyó en la Fase 1 del `ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2.md`,
> siguiendo la rutina de fase segura definida en `PLAN_EJECUCION_V2.md` §1 y el andamiaje de la
> Fase 0 (`WALKTHROUGH_FASE0.md`).
>
> **Rama:** `feature/fase1-medicos-credenciales`, creada sobre `main` (la Fase 0 se fusionó en
> `main` vía PR #115). Costo AWS: **cero recursos nuevos** — solo PostgreSQL, backend y CI.

---

## 1. Qué entrega la Fase 1

Desacopla la **identidad profesional** del consultorio. Hoy hay un médico por tenant, pero la
firma legal (NOM-004 §5.8) ya no se ata para siempre a `tenants`. Se introducen dos tablas
nuevas y **un solo punto** por el que los tres flujos de firma leen la credencial.

- `medicos` — identidad profesional (`tenant_id`, `nombre_completo`, `rfc`, `activo`, …).
- `medico_credenciales` — credenciales (`numero`, `numero_normalizado`, `tipo`, `especialidad`,
  `es_predeterminada`, `activa`, `verificada`, …). Una por médico marcada como predeterminada.

Regla de oro respetada (§1.1): **el backfill toca solo tablas nuevas**, así que el trigger de
inmutabilidad de notas firmadas nunca entra en juego.

---

## 2. La migración (`efb69dbb7dfb`)

Sigue la rutina de fase segura (esquema + backfill chico, reversible):

1. **Esquema primero, sin RLS.** Crea ambas tablas e índices. `medico_credenciales` lleva su
   **propia** `tenant_id` porque RLS no puede seguir el FK a `medicos` (§1.2).
2. **Backfill como owner, antes de forzar RLS.** Un `medico` + una credencial predeterminada por
   tenant, tomando `nombre_medico`/`cedula`/`especialidad` de `tenants`. El orden importa:
   `FORCE ROW LEVEL SECURITY` aplica **también al owner**, y `app.current_tenant` no está fijado
   durante la migración — así que el backfill corre **antes** de forzar RLS (mismo patrón que la
   migración de clinical files). Guardas `NOT EXISTS` → idempotente.
3. **RLS + política + grants.** `ENABLE` + `FORCE` + `tenant_isolation_<tabla>` con `USING`/`WITH
   CHECK` sobre `current_setting('app.current_tenant', true)::uuid`; `GRANT SELECT, INSERT, UPDATE`
   a `medrecord_app`.
4. **Protección de borrado (§5.1).** `REVOKE DELETE` + trigger `prevent_<tabla>_deletion`
   (reusa la función compartida `prevent_clinical_deletion`). Una credencial usada en un documento
   firmado se **desactiva, nunca se borra**.

**Índices únicos parciales** (a prueba de carreras, no validación transaccional):

- `uq_credencial_numero_por_medico (medico_id, numero_normalizado)` — número único por médico.
- `uq_credencial_predeterminada_por_medico (medico_id) WHERE es_predeterminada AND activa` — una
  sola predeterminada activa por médico.

Normalización de número: `upper(regexp_replace(numero, '\s+', '', 'g'))` en SQL, espejo exacto de
`app.core.credenciales.normalize_credential_number` en Python (mantener en lockstep).

La migración es **reversible** (`downgrade -1` / `upgrade head`, lo que CI ya verifica).

---

## 3. Un solo adaptador de firma

Los tres flujos que estampan la identidad del médico (`consentimientos._render_content`/emisión,
`notas.firmar` / `_build_legal_note_payload`, `recetas` firma) consumen **un** adaptador:

```python
# app/services/credenciales.py
cred = await get_credencial_para_firma(db, tenant)   # -> CredencialFirma(nombre, cedula, especialidad)
```

Resuelve la credencial predeterminada activa del tenant, con **fallback por campo** a las columnas
de `tenants` y fallback completo si el tenant aún no tiene credencial. Como `tenants.cedula` se
mantiene sincronizada con la credencial predeterminada (§1.3), la salida es **byte a byte
idéntica** a la anterior: el texto de consentimientos y las firmas no cambian.

**Doble escritura (§1.3):**

- **Onboarding** crea el médico + credencial predeterminada en la **misma transacción** que el
  tenant (`provision_medico_para_tenant`), fijando el contexto RLS al nuevo tenant antes de
  insertar (onboarding corre bajo un contexto placeholder).
- **`update_profile`** sincroniza la credencial predeterminada al editar cédula/especialidad
  (`sync_credencial_predeterminada`). `medico_credenciales` **no** tiene trigger de inmutabilidad
  de UPDATE, así que editar la credencial en su lugar es válido (a diferencia de las notas firmadas).

---

## 4. Verificación (las dos redes de la Fase 0)

**Pre-deploy (CI, esquema migrado real).** `tests/integration/test_medicos_credenciales.py`
(`@pytest.mark.migration_schema`, 9 pruebas): aislamiento RLS entre tenants, INSERT cross-tenant
rechazado, ambos índices únicos parciales, `REVOKE DELETE` + trigger, y provisión/sincronización.
`conftest.py` replica el backfill de médicos tras sembrar tenants, para reproducir el estado real
post-migración.

**Post-deploy (prod, read-only).** Nuevo verificador `verify_medicos` en `verify_registry.py`
(registrado en `_VERIFIERS`, opción `medicos` añadida a `ops-verify.yml`). Afirma, sin PHI:

- `medicos`/`medico_credenciales` con RLS + política + sin DELETE de la app.
- **Backfill completo:** todo tenant tiene médico; todo tenant con cédula tiene credencial
  predeterminada.
- **Sincronía §1.3:** `tenants.cedula` = número normalizado de la credencial predeterminada.

Los conteos cross-tenant funcionan porque el verificador corre como el rol de conexión que
**omite RLS** (el mismo que usa `verify_rls`, no degradado a `medrecord_app`).

---

## 5. `release_cedula` al día con el nuevo modelo (§1.3)

Tras el backfill, **todo** tenant tiene médico + credencial, y esas filas están protegidas contra
borrado. Sin cambios, `release_cedula` (que libera una cédula borrando un tenant **huérfano**) ya
no podría liberar ni una cédula genuinamente huérfana. Ajustes:

- **`inspect`** clasifica `medicos`/`medico_credenciales` como **identidad, no evidencia clínica**:
  se muestran en `related_rows` pero no cuentan para `has_data`.
- **`release`** deshabilita **transaccionalmente** los dos triggers `prevent_*_deletion`
  (solo el owner puede), retira la identidad backfilled no usada y borra el tenant. La red de
  seguridad se conserva: si el tenant tiene datos clínicos reales, el DELETE viola la FK a
  `pacientes`/etc., **todo se revierte** (incluidos triggers y filas de identidad) y se lanza
  `TenantHasDataError`. Nunca se pierde la identidad de un tenant real.

Verificado a mano: huérfano → liberado (triggers reactivados); tenant con paciente → rechazado,
exit 1, nada borrado, triggers intactos.

---

## 6. Cómo correr la verificación localmente

Igual que la Fase 0 (ver `WALKTHROUGH_FASE0.md` §5), más:

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord_migrations"

# Suite de esquema migrado real (incluye médicos/credenciales)
TEST_SCHEMA_MODE=migrations JWT_DEV_SECRET=testing-secret-key-123 CLERK_SECRET_KEY=testing-clerk-key-123 \
  .venv/bin/pytest -m migration_schema -v

# Verificador de prod (read-only) contra la BD migrada
ENVIRONMENT=development PYTHONPATH=. .venv/bin/python -c \
  "import json; from scripts.verify_registry import run_verify; print(json.dumps(run_verify('medicos'), default=str, indent=2))"
```

En prod, tras el deploy: workflow **Ops — Verify** con `action=medicos` (requiere aprobación del
GitHub Environment `production`).

---

## 7. Criterio de "listo para deploy" (checklist de la fase)

- [x] Migración reversible (`downgrade -1` / `upgrade head`).
- [x] Test de integración verde con **migración real** (RLS, unicidades, protección de borrado,
      backfill, provisión/sincronización).
- [x] Verificador extendido (`verify_medicos`) + wiring de workflow.
- [x] Adaptador único consumido por los tres flujos de firma; salida idéntica (fallback + §1.3).
- [x] `release_cedula` + `release-cedula.yml` funcionan contra el nuevo modelo.
- [x] Onboarding/`update_profile` en doble escritura, `tenants.cedula` sincronizada.
- [x] Suite rápida (59) y `migration_schema` (12) verdes; ruff limpio.
- [ ] **Snapshot de RDS antes del deploy** (paso operativo, al desplegar).
- [ ] Regresión de `firmar` end-to-end en prod tras el deploy.

Los campos de firma en `tenants` **no** se retiran aquí — esa es la última migración del proyecto
(Fase 8), tras validar producción.
