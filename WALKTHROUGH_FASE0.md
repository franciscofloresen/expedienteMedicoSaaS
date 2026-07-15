# Walkthrough — Fase 0: Andamiaje de verificación y saneamiento RLS

> Narrativa de lo que se construyó en la Fase 0 del `ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2.md`,
> por qué, cómo funciona y cómo usarlo. Complementa a `PLAN_EJECUCION_V2.md` (que define la
> estrategia) con el detalle de ejecución real.
>
> **Rama:** `chore/fase0-verification-scaffolding` (creada sobre `feature/uxui-redesign`, **no**
> sobre `main` — `main` está 79 commits atrás y no tiene clinical file storage, el job
> `migration-check`, ni `verify_file_storage`). El PR de esta rama va contra
> `feature/uxui-redesign`.

---

## 1. Por qué existe la Fase 0

El roadmap V2 parte de cinco restricciones reales del código (ver §1 del plan). Dos de ellas
hacen que desplegar migraciones sea peligroso:

- **No hay ambiente de staging** (decisión tomada). Lo que se prueba local es lo único antes de prod.
- **Los tests usan `create_all`, no migraciones** (§1.4). Triggers, políticas RLS y backfills
  viven en SQL crudo dentro de las migraciones Alembic; `create_all` nunca los emite, así que la
  suite jamás los ejercita.

El resultado: el esquema que los tests validaban **no era** el que corría en producción. La Fase 0
cierra esa brecha y deja una **rutina repetible** para que cada fase futura con migración se
despliegue sin romper nada.

---

## 2. El problema concreto que se encontró

Al abrir el capó aparecieron tres tipos de *drift* (deriva entre intención y realidad):

1. **Drift test↔migración.** `conftest.py` construía el esquema con `create_all` y **copiaba a
   mano** políticas RLS y triggers de inmutabilidad. Esa copia ya no coincidía con las
   migraciones reales (p. ej. la política de test era `tenant_isolation_policy FOR ALL TO
   medrecord_app`, mientras la migración crea `tenant_isolation_<tabla>` sin cláusula de rol). El
   test de inmutabilidad reinstalaba el trigger por copia manual — vulnerable a divergencia.

2. **Drift de FORCE RLS.** `consentimientos` y `recetas` tenían RLS habilitado y con política,
   pero habían **perdido `FORCE ROW LEVEL SECURITY`**: migraciones posteriores las recrearon con
   `GRANT ALL` sin re-forzar (la migración original sí forzaba `consentimientos`).

3. **Drift de delete-protection.** Esas mismas recreaciones con `GRANT ALL` devolvieron el
   privilegio `DELETE` sobre documentos clínicos (`consentimientos`, `recetas`) al rol de la app,
   deshaciendo el `REVOKE DELETE` original — un riesgo de NOM-004 §5.14 (conservación).

**Causa raíz común:** *una migración que recrea una tabla con `GRANT ALL` deshace en silencio el
`REVOKE DELETE` / `FORCE RLS` de una migración anterior.* Sin una prueba que corra el esquema
migrado real, nadie lo veía.

---

## 3. Lo que se construyó (6 commits)

```
ea8d8ef  fix(db): complete delete-protection on pacientes and verification_tokens
4d053af  fix(db): block hard-delete of recetas and consentimientos (NOM-004 §5.14)
211bad2  fix(db): restore FORCE ROW LEVEL SECURITY on consentimientos and recetas
8e2e8d3  docs: restore compliance matrix as a living, evidence-based matrix
363f841  feat(ops): unified verify_* dispatch contract + ops-verify workflow
19dc489  test(ci): run trigger/RLS regression tests against the real migrated schema
```

### 3.1 Red pre-deploy: tests contra el esquema migrado real (`19dc489`)

- `backend/tests/conftest.py` gana un modo **aditivo** `TEST_SCHEMA_MODE=migrations`: en vez de
  `create_all`, corre `alembic upgrade head` (RLS, grants y triggers reales de producción). El
  default sigue siendo `create_all`, así que la suite rápida no cambia.
- Los tests sensibles a trigger/RLS se marcan `@pytest.mark.migration_schema`.
- El job `migration-check` de `.github/workflows/ci.yml` corre `pytest -m migration_schema` contra
  ese esquema migrado. Es la **única** red que ejecuta el DDL real (§1.4).
- El test de inmutabilidad de notas ahora corre contra el **trigger real de Alembic**, no contra
  una copia a mano.

### 3.2 Red post-deploy: contrato unificado `verify_*` (`363f841`)

- `backend/scripts/verify_registry.py` es el contrato: un registro `action → verificador`, con un
  *envelope* uniforme (`ok/action/checks/warnings/counts`), **read-only** y **sin PHI**.
- El Lambda despacha `{"verify": "<action>"}` (una sola rama nueva en `app/main.py`, las 8 ramas
  admin existentes quedan intactas).
- `.github/workflows/ops-verify.yml` es **un** workflow parametrizado que lo invoca tras el deploy
  y falla si algún check no pasa. Crece agregando una opción de `action`.
- Primer verificador: **`rls`** — chequeo estructural read-only (`pg_catalog`) que corre incluso en
  prod, a diferencia de `scripts/verify_rls.py`, que se niega a correr en prod porque escribe datos
  semilla.

### 3.3 Matriz de cumplimiento viva (`8e2e8d3`)

- `docs/compliance_matrix.md` estaba **borrada**. Se restauró en el formato del §14.1: estados
  honestos (`no evaluado / parcial / implementado / verificado independiente` — **ninguno** es
  "verificado independiente" aún, pendiente del pentest de Fase 9), con los campos por requisito
  (interpretación, responsable, control, prueba, evidencia, riesgo residual).
- Se corrigió el *drift documental*: la matriz vieja afirmaba **Aurora** (real: RDS PostgreSQL),
  **Cognito** (real: Clerk) y triggers de auditoría a nivel fila (real: `AuditMiddleware` a nivel
  request). Y se eliminó el estado binario "Cumple ✅" sin evidencia.

### 3.4 Los fixes que el andamiaje destapó (`211bad2`, `4d053af`, `ea8d8ef`)

- **`211bad2`** — restaura `FORCE ROW LEVEL SECURITY` en `consentimientos` y `recetas`.
- **`4d053af`** — bloquea el hard-delete de `consentimientos` y `recetas` (`REVOKE DELETE` +
  triggers `prevent_*_deletion`) y **extiende el verificador** con un check de delete-protection
  por tabla, para que esta clase de drift se cace en CI y en prod de ahí en adelante.
- **`ea8d8ef`** — cierra los dos últimos huecos: trigger anti-DELETE en `pacientes` (ya tenía
  `REVOKE DELETE`) y `REVOKE DELETE` en `verification_tokens` (ancla de integridad de firmas).

---

## 4. Estado final de protección por tabla

Toda tabla clínica quedó con **doble protección** (rol + trigger), igual que `notas`:

| Tabla | FORCE RLS | App no puede DELETE | Trigger anti-DELETE |
|---|:--:|:--:|:--:|
| pacientes | ✅ | ✅ | ✅ |
| expedientes | ✅ | ✅ | ✅ |
| notas | ✅ | ✅ | ✅ |
| consentimientos | ✅ | ✅ | ✅ |
| recetas | ✅ | ✅ | ✅ |
| verification_tokens | — | ✅ | — *(integridad, no doc clínico)* |

`citas`, `message_logs`, `reminders` son borrables **por diseño** (operacionales: las citas se
cancelan por `estado`, los logs/recordatorios son transitorios). Documentado como aceptado.

> **Nota sobre inmutabilidad de UPDATE en consentimientos:** *no* se agregó todavía un trigger de
> inmutabilidad de UPDATE (espejo del de notas). Es un ítem de **Fase 5** que debe diseñarse para
> permitir el UPDATE de `verification_token_id` **antes** del bloqueo — si no, se repite el bug del
> 500 en `firmar`. Ver `firmar-500-cors-is-schema-drift` en memoria.

---

## 5. Cómo correr la verificación localmente

Requisitos: Docker corriendo, `backend/.venv` y el Postgres de `docker-compose.yml` (puerto 5433).

```bash
cd backend
export PGPASSWORD=postgres

# 1. DB migrada limpia + rol de la app (igual que el CI)
psql -h localhost -p 5433 -U postgres -d medrecord -c "DROP DATABASE IF EXISTS medrecord_migrations;"
psql -h localhost -p 5433 -U postgres -d medrecord -c "CREATE DATABASE medrecord_migrations;"
psql -h localhost -p 5433 -U postgres -d medrecord_migrations -c \
  "GRANT CONNECT ON DATABASE medrecord_migrations TO medrecord_app;"
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord_migrations"

# 2. Correr la cadena de migraciones real
ENVIRONMENT=development .venv/bin/alembic upgrade head

# 3. Verificar aislamiento RLS estructural (lo mismo que corre ops-verify en prod)
ENVIRONMENT=development PYTHONPATH=. .venv/bin/python scripts/verify_rls.py

# 4. Tests de trigger/RLS contra el esquema migrado real
TEST_SCHEMA_MODE=migrations JWT_DEV_SECRET=testing-secret-key-123 CLERK_SECRET_KEY=testing-clerk-key-123 \
  .venv/bin/pytest -m migration_schema -v
```

La suite rápida de siempre (sin migraciones) sigue igual:

```bash
# crea medrecord_test y corre todo en modo create_all
.venv/bin/pytest -q          # los tests migration_schema estructurales se saltan aquí
```

En prod, tras un deploy, se dispara manualmente el workflow **Ops — Verify** con `action=rls`
(read-only, requiere aprobación del GitHub Environment `production`).

---

## 6. La rutina de fase segura (para cada fase futura)

Toda fase con migración sigue estos pasos (detalle en `PLAN_EJECUCION_V2.md` §1):

1. Diseñar la migración como **DDL rápido + backfill chico**. Regla de oro: **cero UPDATE a filas
   firmadas**; relaciones nuevas en tablas hijas/laterales.
2. Definir el `verify_<fase>` que se agregará.
3. Migración Alembic: **solo esquema** (tablas, columnas, índices, `FORCE RLS` + política
   `tenant_isolation_<tabla>`, `REVOKE DELETE` si es tabla clínica).
4. Test de integración marcado `@pytest.mark.migration_schema` que ejercita trigger/RLS/backfill.
5. Extender `scripts/verify_rls.py` / el verificador con la(s) tabla(s) nueva(s).
6. Endpoints/adaptador con **fallback temporal** al modelo viejo, detrás de gate por plan
   (`core/plans.py`) o env var.
7. **Snapshot de RDS** antes del deploy.
8. Deploy → migración → `verify_rls` en prod → payload `verify_<fase>`; si algo falla, restore.
9. Importación de datos (si aplica) como payload admin idempotente, **después** del deploy.

### Cómo enchufar un verificador nuevo

```python
# backend/scripts/verify_registry.py
async def verify_medicos() -> dict[str, Any]:
    ...  # checks read-only, sin PHI; usa _check() y _envelope("medicos", checks)

_VERIFIERS = {
    "rls": verify_rls,
    "medicos": verify_medicos,   # <-- una línea
}
```

Luego agregar `medicos` a las opciones de `action` en `.github/workflows/ops-verify.yml` y un test
`@pytest.mark.migration_schema` que llame a `verify_medicos()` contra el esquema migrado.

---

## 7. Qué garantiza esto

- El **DDL real** (triggers, RLS, grants) se ejercita en CI antes de cada deploy — no una
  aproximación copiada a mano.
- La **causa raíz** del drift (`GRANT ALL` deshaciendo `REVOKE`/`FORCE`) ya no puede reaparecer en
  silencio: el verificador `rls` la caza como check duro, y `test_verify_rls_structure.py` es el
  guardián de regresión.
- Hay una **verificación read-only apta para prod** post-deploy, y un contrato uniforme para que
  cada fase agregue la suya sin duplicar plomería.
- La **matriz de cumplimiento** dice la verdad, con evidencia (migraciones citadas) y sin
  afirmaciones autoproclamadas.

Costo de todo lo anterior: **cero recursos AWS nuevos** — son cambios de PostgreSQL y CI, dentro de
la disciplina de USD 150/mes.
