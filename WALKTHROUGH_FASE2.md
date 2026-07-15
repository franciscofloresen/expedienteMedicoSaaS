# Walkthrough — Fase 2: Encuentros clínicos y primera vez/evolución

> Narrativa de lo que se construyó en la Fase 2 del `ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2.md`,
> siguiendo la rutina de fase segura de `PLAN_EJECUCION_V2.md` §1 y el andamiaje de la Fase 0.
>
> **Rama:** `feature/fase2-encuentros`, creada sobre `main` (Fase 1 fusionada vía PR #116).
> Costo AWS: **cero recursos nuevos** — solo PostgreSQL, backend y CI.

---

## 1. Qué entrega la Fase 2

Separa la **atención real** (el encuentro) de la **agenda** (la cita). Una cita es un hueco
programado; un encuentro es lo que efectivamente pasó. Separarlos evita el error clásico de
contar una cita cancelada como "primera consulta".

- `encuentros_clinicos` — tabla nueva tenant-scoped: `paciente_id`, `expediente_id`,
  `cita_id` (opcional), `medico_id`, `credencial_id` (hasta la firma), `tipo`
  (`primera_vez | subsecuente | procedimiento | urgencia | otro`), `estado`
  (`programado | iniciado | completado | cancelado`), `clasificacion_origen`
  (`automatica | manual | migracion`), `nota_inicial_id`.
- `notas.encuentro_clinico_id` — columna **nullable** nueva, escrita **solo al crear** notas.

Es "toca solo tablas nuevas" (§3 del plan): una tabla nueva + un índice único parcial + una
columna nullable. Sin backfill sobre filas clínicas existentes — la clase de cambio que nunca
ha roto prod aquí.

---

## 2. La migración (`a2f4c6e8b0d1`)

Sigue la rutina de fase segura (solo esquema, reversible):

1. **Tabla `encuentros_clinicos`** con sus tres `CHECK` (tipo/estado/clasificacion_origen),
   índices por `(tenant_id, paciente_id, estado)` y `fecha_inicio`, y su `tenant_id` propia
   (RLS no sigue FKs — §1.2).
2. **Índice único parcial (§3):** `uq_encuentro_primera_vez UNIQUE (tenant_id, paciente_id)
   WHERE tipo = 'primera_vez' AND estado = 'completado'`. Este índice —no una validación
   transaccional— es el enforcement real de "una sola primera vez". A prueba de carreras, y
   una `primera_vez` **cancelada** nunca bloquea una genuina (solo cuentan las completadas).
3. **`ADD COLUMN` nullable en `notas`** (`encuentro_clinico_id`). Es metadata-only, sin
   default → **no toca ninguna fila** → el trigger de inmutabilidad `notas_signed_immutable`
   (que es `FOR EACH ROW` en `UPDATE`) **jamás se dispara** (§1.1). Ese es exactamente el
   incidente 500/CORS de la firma, evitado por diseño.
4. **RLS + política + grants**, luego **`REVOKE DELETE` + trigger
   `prevent_encuentros_clinicos_deletion`** (reusa la función compartida
   `prevent_clinical_deletion`): un encuentro es evidencia clínica, se cancela, nunca se borra.

**Regla de oro respetada (§1.1):** cero UPDATE a notas firmadas. El vínculo nota↔encuentro
para notas nuevas vive en `notas.encuentro_clinico_id` (escrito al crear); para notas
históricas viviría solo del lado del encuentro (`nota_inicial_id`), sin tocar la nota firmada.

El ciclo de FK `notas ⇄ encuentros_clinicos` se rompe con `use_alter=True` en el lado del
encuentro, para que `create_all` (modo de test rápido) pueda ordenar la creación. En la
migración SQL no hay ciclo: `encuentros_clinicos` se crea primero y `notas` recibe su columna
después con `ADD COLUMN`.

Verificado localmente: `upgrade head` → `downgrade -1` → `upgrade head` limpio (lo que el job
de CI también round-trip-ea).

---

## 3. Backend: encuentros detrás de la agenda existente

`app/services/encuentros.py`:

- `sugerir_tipo_encuentro(db, paciente_id)` — `primera_vez` si el paciente no tiene ningún
  encuentro **completado**, si no `subsecuente`. Es una **sugerencia**; la decisión definitiva
  ocurre al completar, y el índice parcial es el guardián real (§3).
- `completar_encuentro(db, encuentro)` — marca `completado` dentro de un `SAVEPOINT`; si
  completar una `primera_vez` choca con el índice, traduce el `IntegrityError` a
  `PrimeraVezDuplicadaError` → **409 legible**, nunca un 500 crudo.

`app/api/v1/encuentros.py` (montado en `/api/v1/encuentros`, sin gate de plan — igual que
`citas`, se puede gate-ar después):

- `GET /sugerencia?paciente_id=` — tipo sugerido.
- `POST /` — crea el encuentro; valida que el expediente pertenezca al tenant (RLS),
  resuelve el `medico_id` del tenant, y **rechaza generar un encuentro desde una cita
  cancelada** (`estado == 'Cancelada'`).
- `POST /{id}/iniciar`, `POST /{id}/completar`, `GET /`, `GET /{id}`.

**Vínculo create-only en notas (§1.1):** `NotaCreate` gana un `encuentro_clinico_id` opcional
que `create_nota` escribe al insertar. `firmar_nota` y `update_nota` **no se tocan** — una nota
firmada nunca recibe el vínculo por UPDATE.

---

## 4. Verificación (las dos redes de la Fase 0)

**Pre-deploy (CI, esquema migrado real).** `tests/integration/test_encuentros.py`
(`@pytest.mark.migration_schema`, 7 pruebas): aislamiento RLS entre tenants, INSERT
cross-tenant rechazado, `REVOKE DELETE`, sugerencia primera_vez→subsecuente, la
`primera_vez` cancelada que no cuenta, y —la prueba estrella de la aceptación (§264)— la
**concurrencia**: dos transacciones que se solapan compitiendo por completar la `primera_vez`
del mismo paciente; **exactamente una gana**, la otra choca con `uq_encuentro_primera_vez`.
Esa es la garantía libre de carreras que la validación transaccional no podía dar (§3). La
**regresión de `firmar`** (crear → firmar → verificar) sigue verde, obligatoria porque
tocamos el esquema de `notas`.

**Post-deploy (prod, read-only).** Nuevo `verify_encuentros` en `verify_registry.py`
(registrado en `_VERIFIERS`, opción `encuentros` añadida a `ops-verify.yml`). Afirma, sin PHI:

- `encuentros_clinicos` con RLS + política + FORCE + sin DELETE de la app.
- El índice parcial `uq_encuentro_primera_vez` **existe** (su ausencia permitiría dos primeras
  consultas en silencio).
- Invariante de datos: **≤1 `primera_vez` completada** por `(tenant, paciente)`.

Además, `encuentros_clinicos` se añadió a `_FORCE_EXPECTED` y `_DELETE_PROTECTED` del
verificador acumulativo `verify_rls`, así que el chequeo estructural genérico también lo cubre.

---

## 5. Cómo correr la verificación localmente

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord_migrations"

# Suite de esquema migrado real (incluye encuentros + regresión de firmar)
TEST_SCHEMA_MODE=migrations JWT_DEV_SECRET=testing-secret-key-123 CLERK_SECRET_KEY=testing-clerk-key-123 \
  .venv/bin/pytest -m migration_schema -v

# Verificador de prod (read-only) contra la BD migrada
ENVIRONMENT=development PYTHONPATH=. .venv/bin/python -c \
  "import json; from scripts.verify_registry import run_verify; print(json.dumps(run_verify('encuentros'), default=str, indent=2))"
```

En prod, tras el deploy: workflow **Ops — Verify** con `action=encuentros` (requiere
aprobación del GitHub Environment `production`).

---

## 6. Manejo del 409 en el frontend (conflicto conciliable, no error opaco)

El índice parcial solo guarda `estado='completado'`, así que dos `primera_vez` pueden
existir en `programado`/`iniciado` y el choque aparece al **completar** la segunda. Para que
la UI lo trate como conflicto conciliable —y no lo confunda con el 409 terminal de un
encuentro "cancelado"— el backend devuelve un **409 estructurado**:

```json
{ "detail": { "code": "primera_vez_duplicada", "message": "El paciente ya tiene una consulta de primera vez completada." } }
```

- **Backend** (`api/v1/encuentros.py`): la `PrimeraVezDuplicadaError` se traduce a ese
  `detail` con `code` legible por máquina; el `message` sigue siendo mostrable.
- **Cliente** (`services/api.ts`): `fetchClient` ahora preserva `error.code` de
  `detail.code`; `encuentrosApi` expone `create/iniciar/completar/list/sugerencia`, y el guard
  `isPrimeraVezConflict(error)` detecta el caso (`status === 409 && code ===
  'primera_vez_duplicada'`). El futuro componente re-consulta y ofrece completar como
  `subsecuente` en vez de mostrar un error crudo.
- **Prueba** (`test_encuentros.py::test_completar_segunda_primera_vez_returns_conflict_code`):
  crea paciente→expediente→dos `primera_vez` vía HTTP, completa la primera (200) y afirma que
  la segunda devuelve 409 con `detail.code == 'primera_vez_duplicada'` — el contrato exacto del
  que depende el guard.

`tipo` sigue siendo inmutable por endpoint hoy: "reconciliar como subsecuente" en la UI
implicará un endpoint de **corrección manual de `tipo`** (con `motivo_correccion`, ya en el
modelo) cuando se construya el componente. Registrado como `[DEUDA FASE 2]` en el roadmap V2
(sección Fase 2).

## 7. Criterio de "listo para deploy" (checklist de la fase)

- [x] Migración reversible (`upgrade head` / `downgrade -1` / `upgrade head`).
- [x] Test de integración verde con **migración real** (RLS, índice parcial, protección de
      borrado, sugerencia, concurrencia).
- [x] **Prueba explícita de concurrencia** contra el índice parcial (§264).
- [x] Verificador extendido (`verify_encuentros`) + `encuentros_clinicos` en los sets de
      `verify_rls` + wiring de `ops-verify.yml`.
- [x] Vínculo `encuentro_clinico_id` **solo al crear** notas; `firmar`/`update` intactos.
- [x] Regresión de `firmar` end-to-end verde (esquema de `notas` tocado).
- [x] Suite rápida (create_all) y `migration_schema` verdes; ruff limpio.
- [ ] **Snapshot de RDS antes del deploy** (paso operativo, al desplegar).
- [ ] Regresión de `firmar` end-to-end en prod tras el deploy + `ops-verify action=encuentros`.

---

## 8. Fuera de alcance (deuda registrada)

- **`compliance_matrix.md`** sigue en el formato binario "Cumple ✅" heredado. Pasarla a la
  matriz viva (`no evaluado/parcial/implementado/verificado independiente`) es una tarea
  transversal separada (`PLAN_EJECUCION_V2` §5 y §7.2), no de la Fase 2. La Fase 2 no agrega
  una primitiva criptográfica/de integridad nueva mapeable a una fila NOM; el encuentro es
  estructura de clasificación de la atención, así que no se fuerza una fila en el formato
  deprecado.
- La **UI visible** de encuentros (etiqueta primera_vez/subsecuente y precarga de
  historia/evolución, V1 §7.2) se aborda cuando el flujo se conecte; el backend ya expone
  `/sugerencia` y la **capa de servicio del frontend ya está lista** (ver §6). El componente
  visual solo tiene que consumir `encuentrosApi` y ramificar con `isPrimeraVezConflict`.
- **`medico_id` asume un médico por tenant.** `create_encuentro` resuelve el médico con
  `_resolve_medico_id` (LIMIT 1 activo), correcto hoy (Fase 1 estableció un médico por tenant)
  y a prueba de fallos (solo hay uno que elegir). Cuando lleguen varios médicos, el endpoint
  debe aceptar `medico_id` explícito — registrado en el roadmap V2, **Fase 14** (`[DEUDA FASE 2]`).
- **`credencial_id`** queda `NULL` hasta que se firme la nota del encuentro; poblarlo se
  registró en el roadmap V2, **Fase 12** (`[DEUDA FASE 2]`).
