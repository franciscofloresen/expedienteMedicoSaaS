# Walkthrough — Fase 3: CIE-10 completo y diagnósticos estructurados

> Narrativa de lo que se construyó en la Fase 3 del `ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2.md`,
> siguiendo la rutina de fase segura de `PLAN_EJECUCION_V2.md` §1 y el andamiaje de la Fase 0.
>
> **Rama:** `feature/fase3-cie10-diagnosticos`, creada sobre `feature/fase2-encuentros`.
> Costo AWS: **cero recursos nuevos** — solo PostgreSQL (extensión `pg_trgm`, sin infra),
> backend y CI.

---

## 1. Qué entrega la Fase 3

Reemplaza el texto libre `notas.diagnostico_cie10` (`String(255)`) y el catálogo `cie10` de
3 columnas con búsqueda `ILIKE` ingenua, por:

- **Catálogo CIE-10 real** (versión mexicana DGIS/SSA, 14 486 códigos) con búsqueda **sin
  acentos** vía índice GIN trigram (`pg_trgm`, cero infra).
- **Diagnósticos estructurados múltiples por nota** (`nota_diagnosticos`): varios códigos,
  ordenados, con snapshot de la descripción/versión del catálogo, y **un solo principal**
  por nota (índice único parcial).

Es "toca solo tablas nuevas + dato de referencia" (§3 del plan): una tabla nueva
tenant-scoped + columnas nullable sobre `cie10` (referencia compartida, sin RLS). **Cero
UPDATE a notas firmadas** — `nota_diagnosticos` apunta *hacia* la nota; la nota nunca se
modifica (§1.1). La clase de cambio que nunca ha roto prod aquí.

---

## 2. La migración (`b3d5e7f9c1a2`)

Sigue la rutina de fase segura (solo esquema, reversible):

1. **`CREATE EXTENSION IF NOT EXISTS pg_trgm`** — disponible en RDS PG15, sin infra. La
   migración corre con el rol master (superusuario), que puede crearla.
2. **Extender `cie10`** (referencia compartida, **sin RLS** — §1.2): columnas
   `normalized_description`, `chapter_code/description`, `group_code`, `category_code`,
   `parent_code`, `selectable`, `active`, `catalog_version`, `source`, fechas. Todas
   nullable/defaulted → `ADD COLUMN` metadata-only, **no toca las filas existentes**.
3. **Índice GIN trigram** `ix_cie10_norm_desc_trgm` sobre `normalized_description`. La
   normalización se hace en **Python** (importador + endpoint), NO con `unaccent()` en la
   expresión del índice (no es immutable — §3).
4. **Tabla `nota_diagnosticos`** (tenant-scoped, `tenant_id` propia — §1.2): `nota_id`,
   `cie10_code`, `orden`, `es_principal`, `certeza` (`confirmado|presuntivo|descartado`),
   `descripcion_snapshot`, `version_snapshot`, auditoría. RLS `ENABLE`+`FORCE` + política
   `tenant_isolation_nota_diagnosticos` + `REVOKE DELETE` + trigger
   `prevent_nota_diagnosticos_deletion` (reusa la función compartida
   `prevent_clinical_deletion`). Índice único parcial `uq_nota_diagnostico_principal
   UNIQUE (nota_id) WHERE es_principal` — un solo principal por nota, a prueba de carreras.

Verificado localmente: `upgrade head` → `downgrade -1` → `upgrade head` limpio, incluyendo
el create/drop de `pg_trgm` (lo que el job de CI también round-trip-ea).

---

## 3. El catálogo: prep offline + importador idempotente

El CSV crudo de la SSA son 5.6 MB / 76 columnas. No entra al repo.

- **Prep (offline, una vez):** `scripts/prepare_cie10_catalog.py` lee el crudo y escribe
  `app/data/cie10_catalog.csv.gz` (**184 KB**, 9 columnas). Transformaciones:
  - `CATALOG_KEY` → código clínico canónico: `A000` → `A00.0`; **`I10X` → `I10`** (la `X`
    es el relleno DGIS de "sin subdivisión"; el código codificable es el de 3 caracteres,
    que es el que médicos y notas legadas escriben).
  - `VALID='SI'` → `active`/`selectable`: marca las rúbricas hoja codificables (una
    categoría de 3 caracteres con hijos de 4 queda `NO`, semántica correcta de CIE-10).
- **Importador:** `scripts/import_cie10.py` lee el gz, calcula `normalized_description` con
  el util compartido, y hace `INSERT … ON CONFLICT (code) DO UPDATE` en lotes de 1000.
  Modos `dry-run` (parse + conteos, sin escribir) / `apply`. **Idempotente**: re-correr
  converge al archivo (segunda corrida = 0 insertados, 14 486 actualizados). ~3 s.
- Payload admin `{"import_cie10": "dry-run"|"apply"}` en el handler de `app/main.py`.

---

## 4. Búsqueda y diagnósticos create-only

`app/core/text_normalization.py::normalize_clinical_text` — NFKD → sin diacríticos →
minúsculas → espacios colapsados. **Única fuente de verdad** compartida por el importador
(pobla `normalized_description`) y el endpoint (normaliza `q`), así el índice y la consulta
viven en el mismo espacio.

`app/api/v1/cie10.py` reescrito: `q` mínimo 2 caracteres, `limit` (≤50) y `offset`. Si `q`
parece código (`^[A-Za-z]\d`) → prefijo sobre `code` (con y sin punto: `I10`≈`I10.X`); si
no → trigram/substring sobre `normalized_description` filtrado a `active AND selectable`,
ordenado por `similarity()`.

**Diagnósticos create-only (§1.1):** `NotaCreate` gana `diagnosticos_cie10` opcional;
`create_nota` inserta filas en `nota_diagnosticos` con snapshot del catálogo **al crear**
la nota (servicio `app/services/diagnosticos.py`). `firmar_nota` y `update_nota` **no se
tocan**. El free-text `diagnostico_cie10` se conserva por compatibilidad. Dos principales
en un payload → 422 legible (y el índice parcial es el guardián real).

**Extracción de legado (§1.1):** `scripts/extract_legacy_diagnosticos.py` parsea un código
del `notas.diagnostico_cie10` libre, lo empata al catálogo, y **INSERTA** una fila en
`nota_diagnosticos` apuntando a la nota — **nunca UPDATEa la nota**. Best-effort declarado
(§3); idempotente (salta notas que ya tienen diagnóstico). Payload
`{"extract_legacy_diagnosticos": "dry-run"|"apply"}`.

---

## 5. Verificación (las dos redes de la Fase 0)

**Pre-deploy (CI, esquema migrado real).** `tests/integration/test_cie10_diagnosticos.py`
(`@pytest.mark.migration_schema`, 11 pruebas): aislamiento RLS, INSERT cross-tenant
rechazado, `REVOKE DELETE`, **un solo principal por nota** (índice parcial), búsqueda
trigram sin acentos, código por prefijo/sin punto, diagnósticos **create-only** vía HTTP
(con snapshot), extracción de legado que **no toca la nota**, e **idempotencia del
importador** (dry-run tras apply → 0 inserciones). La **regresión de `firmar`** sigue verde
(la Fase 3 no altera `notas`, así que la superficie del trigger no cambia).

**Post-deploy (prod, read-only).** Nuevo `verify_cie10` en `verify_registry.py` (registrado
en `_VERIFIERS`, opción `cie10` en `ops-verify.yml`). Afirma, sin PHI:

- `nota_diagnosticos` con RLS + política + FORCE + sin DELETE de la app.
- `pg_trgm` instalada y el índice GIN `ix_cie10_norm_desc_trgm` presente.
- Catálogo importado (`cie10` ≥ 10 000 filas) y **ninguna fila activa sin
  `normalized_description`** (sería invisible a la búsqueda).
- Índice parcial `uq_nota_diagnostico_principal` presente e invariante de datos:
  **≤1 principal** por nota.

Además, `nota_diagnosticos` se añadió a `_FORCE_EXPECTED` y `_DELETE_PROTECTED` del
verificador acumulativo `verify_rls`.

---

## 6. Cómo correr la verificación localmente

```bash
cd backend
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5433/medrecord_migrations"
export ENVIRONMENT=development

# (una vez) regenerar el artefacto compacto desde el CSV crudo de la SSA
python -m scripts.prepare_cie10_catalog /ruta/al/catalogo_cie10.csv

# Suite de esquema migrado real (RLS, índice parcial, trigram, create-only, idempotencia)
TEST_SCHEMA_MODE=migrations JWT_DEV_SECRET=testing-secret-key-123 CLERK_SECRET_KEY=testing-clerk-key-123 \
  .venv/bin/pytest -m migration_schema -v

# Importador contra la BD migrada: dry-run → apply → dry-run (idempotencia)
.venv/bin/python -m scripts.import_cie10 dry-run
.venv/bin/python -m scripts.import_cie10 apply
.venv/bin/python -m scripts.import_cie10 dry-run   # would_insert == 0

# Verificador de prod (read-only)
.venv/bin/python -c \
  "import json; from scripts.verify_registry import run_verify; print(json.dumps(run_verify('cie10'), default=str, indent=2))"
```

En prod, tras el deploy: RDS snapshot → migración → `verify_rls` → **Ops — Verify** con
`action=cie10` → payload `import_cie10` (dry-run, luego apply) → `extract_legacy_diagnosticos`
(dry-run, luego apply) → `verify cie10` de nuevo. (Requiere aprobación del GitHub
Environment `production`.)

---

## 7. Criterio de "listo para deploy" (checklist de la fase)

- [x] Migración reversible (`upgrade head` / `downgrade -1` / `upgrade head`, con `pg_trgm`).
- [x] Test de integración verde con **migración real** (RLS, índice parcial, trigram,
      create-only, extracción de legado, idempotencia del importador).
- [x] Importador **re-ejecutable sin duplicados** (dry-run tras apply → 0 inserciones).
- [x] Verificador extendido (`verify_cie10`) + `nota_diagnosticos` en los sets de
      `verify_rls` + wiring de `ops-verify.yml`.
- [x] Diagnósticos **solo al crear** notas; `firmar`/`update` intactos.
- [x] Regresión de `firmar` end-to-end verde (la Fase 3 no altera `notas`).
- [x] Suite rápida (create_all) y `migration_schema` verdes; ruff limpio; frontend compila.
- [ ] **Snapshot de RDS antes del deploy** (paso operativo, al desplegar).
- [ ] Migración → `ops-verify action=cie10` → `import_cie10 apply` →
      `extract_legacy_diagnosticos apply` → `verify cie10` en prod.

---

## 8. Fuera de alcance (deuda registrada)

- **UI del editor de notas para múltiples diagnósticos** (seleccionar varios códigos,
  marcar el principal). El backend acepta `diagnosticos_cie10` y la **capa de servicio del
  frontend ya está lista** (`cie10Api.search` con cancelación de requests obsoletos y caché
  de sesión; `Cie10Search.tsx` adaptado). Solo falta el componente visual que los liste.
  Registrado como `[DEUDA FASE 3]` en el roadmap V2 (mismo patrón que la Fase 2).
- **`catalog_version`** es hoy la constante `CIE-10-MX` sellada por el importador; una tabla
  de release del catálogo versionada se aborda con el retiro de campos legados (Fase 8+).
  Los diagnósticos guardan `version_snapshot`, así que una re-versión nunca reescribe la
  historia. `[DEUDA FASE 3]`.
- **`compliance_matrix.md`** sigue en el formato binario "Cumple ✅" heredado. Pasarla a la
  matriz viva es una tarea transversal separada (`PLAN_EJECUCION_V2` §5). La Fase 3 no
  agrega una primitiva criptográfica/de integridad nueva mapeable a una fila NOM (el
  diagnóstico estructurado es organización de la evidencia, con snapshot), así que no se
  fuerza una fila en el formato deprecado.
