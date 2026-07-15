# Plan de ejecución del Roadmap Clínico V2

> Complemento operativo de `ROADMAP_CLINICO_SIN_INCREMENTO_AWS_V2.md`.
> El roadmap dice **qué** construir y **por qué es viable dentro de USD 150/mes**.
> Este documento dice **cómo desarrollarlo sin romper producción**, con el código
> real como referencia. No repite el roadmap; lo traduce a una rutina de ingeniería
> repetible. Validado contra el árbol en `feature/uxui-redesign` el 2026-07-14.

---

## 0. Verificación: el roadmap es fiel al código

Antes de planear, confirmé que las cinco restricciones del §1 del roadmap son reales:

| Restricción del roadmap | Verificado en código | Estado |
|---|---|---|
| Trigger de inmutabilidad bloquea UPDATE a nota firmada | `notas_signed_immutable` en `a1b2c3d4e5f6_rls_audit_immutability.py:194` lanza excepción si `OLD.es_editable = false` | ✅ Real |
| Toda tabla con `tenant_id` necesita RLS `FORCE` + política | Patrón en misma migración `:61-99`; `REVOKE DELETE` en tablas clínicas `:121-134` | ✅ Real |
| `tenants.cedula` es UNIQUE con operación encima | `tenant.py:27` `unique=True`; `scripts/release_cedula.py` + `.github/workflows/release-cedula.yml` | ✅ Real |
| Tests usan `create_all`, no migraciones | Confirmado; triggers/RLS/backfill quedan fuera de la suite | ✅ Real |
| Importaciones por payload admin, no Alembic | Patrón `upgrade_tenant.py` / `verify_file_storage.py` invocados por workflow | ✅ Real |

Adicionalmente confirmé el punto de partida de cada fase:

- **CIE-10** (`models/cie10.py`) hoy es mínima: `code`, `description`, `category`. La Fase 3
  la extiende en el mismo lugar (PK sigue siendo `code`). No hay tabla paralela que limpiar.
- **Consentimientos** (`api/v1/consentimientos.py:24`) es un `dict` `TEMPLATES` hardcodeado
  con `template_key`. La Fase 4 lo migra a tabla versionada; los emitidos ya guardan
  `contenido_renderizado`, así que no se re-renderizan.
- **Notas** (`models/nota.py`) ya tienen snapshot (`medico_nombre/cedula/especialidad`),
  `es_editable`, `diagnostico_cie10` como `String(255)` texto libre, y ya existe
  `notas_tipo_nota_check` con `historia_clinica`. La Fase 2 no toca el constraint.
- **Feature gating** ya existe en `core/plans.py` (resuelto desde el JWT de Clerk). No se
  construye infraestructura de flags nueva.

**Conclusión:** el roadmap no necesita corrección estructural. Necesita una disciplina de
entrega. Eso es lo que sigue.

---

## 1. La rutina de fase segura (el corazón del "no rompas nada")

Toda fase con migración sigue **exactamente** estos 9 pasos, en orden. Es un checklist,
no una sugerencia. Nace de que no hay staging y los tests no ejecutan migraciones (§1.4).

```
┌─ ANTES DE ESCRIBIR CÓDIGO ─────────────────────────────────────────┐
│ 1. Diseñar la migración como DDL rápido + backfill chico.          │
│    Regla de oro: cero UPDATE a filas firmadas (§1.1).              │
│    Relaciones nuevas → tablas hijas/laterales, nunca columna       │
│    poblada en notas históricas.                                    │
│ 2. Definir el payload verify_<fase> del Lambda admin y qué afirma. │
└────────────────────────────────────────────────────────────────────┘
┌─ DESARROLLO ───────────────────────────────────────────────────────┐
│ 3. Migración Alembic: SOLO esquema (tablas, columnas, índices,     │
│    RLS FORCE + política tenant_isolation_<tabla>, REVOKE DELETE).  │
│ 4. Test de integración que corre la migración REAL (no create_all) │
│    y prueba trigger + RLS + backfill. Única red de seguridad.      │
│ 5. Extender scripts/verify_rls.py con la(s) tabla(s) nueva(s).     │
│ 6. Adaptador/endpoints con fallback temporal al modelo viejo.      │
│    Detrás de gate por plan (core/plans.py) o env var del Lambda.   │
└────────────────────────────────────────────────────────────────────┘
┌─ DESPLIEGUE (el deploy pone página de mantenimiento) ──────────────┐
│ 7. Snapshot manual de RDS antes del deploy (instancia plana).     │
│ 8. Deploy → migración (DDL en segundos) → verify_rls en prod →    │
│    payload verify_<fase> en Lambda admin → si algo falla, restore.│
│ 9. Importación de datos (si aplica) como payload admin vía         │
│    workflow, DESPUÉS del deploy, fuera de la ventana de           │
│    mantenimiento. Idempotente, con dry-run y conteos.             │
└────────────────────────────────────────────────────────────────────┘
```

**Prueba de regresión obligatoria** tras cualquier fase que toque `notas` o
`consentimientos`: ejecutar el flujo `firmar` completo (crear → firmar → verificar). Es el
antecedente del incidente 500/CORS por el trigger de inmutabilidad. Va en el job de CI de
verificación de migraciones.

**Criterio de "listo para deploy" de cada fase:**
`migración reversible + test de integración verde con migración real + verify_rls extendido
+ payload verify_<fase> escrito + snapshot tomado + regresión de firmar verde`.

---

## 2. Andamiaje que se construye UNA vez (Fase 0, habilita todo lo demás)

Estas cuatro piezas son prerequisito. Sin ellas, cada fase reinventa su seguridad.

### 2.1 Job de CI "verificación de migraciones"
Extiende `.github/workflows/ci.yml`: levanta Postgres, corre `alembic upgrade head` (no
`create_all`), y ejecuta la carpeta `tests/integration/` contra esa BD migrada. Aquí viven
las pruebas de trigger, RLS y la regresión de `firmar`. Patrón ya usado en el rollout de
clinical files.

### 2.2 Contrato del Lambda admin `verify_*`
Formalizar el dispatch por `action` que ya usan `release_cedula.py` / `upgrade_tenant.py` /
`verify_file_storage.py`. Cada fase agrega un `verify_<fase>` que devuelve conteos y checks
(no PHI). Un solo workflow parametrizado (`ops-verify.yml`) que recibe `action` como input.

### 2.3 `verify_rls.py` como verificador acumulativo
Hoy verifica `clinical_file` / `tenant_storage_usage`. Se convierte en el verificador
canónico: cada tabla nueva con `tenant_id` agrega su bloque de checks (A ve solo lo suyo,
UPDATE cross-tenant = 0 filas, INSERT cross-tenant rechazado, sin contexto = 0 filas).
Corre en CI (BD migrada) **y** en prod tras cada deploy.

### 2.4 Snapshot + restore ensayado
Documentar el runbook de snapshot manual pre-deploy y **ejecutar una restauración real una
vez** en Fase 0 (obligatorio por §1.4, no opcional). Sin evidencia de restore, el RTO/RPO
del §9.1 es ficción.

**Guardas de costo (Fase 0, una vez):** AWS Budget con alertas a USD 110/130/145, Cost
Anomaly Detection, etiquetas `Project/Environment/Owner/CostCenter`, y S3 Gateway Endpoint
(§13.1 — sin cargo por hora, reduce costo variable del NAT sin tocar la salida a Clerk).

---

## 3. Secuencia de ejecución (orden ejecutivo del §20, con detalle de arranque)

El orden **no** es numérico. Seguridad (Fase 9) corre en paralelo desde el inicio porque es
bloqueo de venta. Recuperación (Fase 10) bloquea lanzamiento general. La secuencia real:

```
Semana:   1─2   3─4   5─6   7─8   9─10  11─12  13─16  17─20  21─24  25+
Núcleo:   [F0][─F1─][─F2─][──F3──][──F4──][F5][F6]
Seguridad:     [────────── F9 (paralelo, bloqueo de venta) ──────────]
Confiab.:                              [── F10 ──][──── F11 ────]
Clínico:                                              [── F12 ──][─ F13 ─]
Adopción:                                                  (pilotos 5–10 médicos)
```

### Bloque A — Núcleo clínico (Fases 0–3): las primeras ~6 semanas

Este bloque es "toca solo tablas nuevas" → riesgo de trigger casi nulo. Es donde empezar.

**Fase 1 — Médicos y credenciales.** Backfill toca solo tablas nuevas (`medicos`,
`medico_credenciales`). Punto delicado: ~30 sitios leen `tenant.cedula/nombre_medico/
especialidad` (`consentimientos._render_content`, `notas.firmar_nota`,
`recetas._build_receta_print_payload`). Se introduce **un** adaptador
`get_credencial_para_firma(tenant)` y los tres flujos lo consumen. En la **misma fase** se
actualiza `release_cedula.py` + `release-cedula.yml` y se mantiene `tenants.cedula`
sincronizada con la credencial predeterminada (§1.3). Los campos de `tenants` NO se retiran
aquí — eso es la última migración del proyecto (Fase 8).

**Fase 2 — Encuentros y primera vez/evolución.** Sin backfill de `encuentro_clinico_id`
sobre notas firmadas: `notas.encuentro_clinico_id` se escribe **solo al crear** notas
nuevas. El enforcement de "una sola primera vez" es un **índice único parcial**
(`UNIQUE (tenant_id, paciente_id) WHERE tipo='primera_vez' AND estado='completado'`), no
validación transaccional. La relación cita→encuentro usa `citas.estado`
(`Programada/Cancelada/Completada`, confirmado en `models/cita.py:38`); cita cancelada nunca
genera encuentro. Aceptación: prueba explícita de concurrencia contra el índice parcial.

**Fase 3 — CIE-10 completo y diagnósticos.** Migración = solo esquema (extender `cie10`,
crear `nota_diagnosticos` con su propia `tenant_id`, `CREATE EXTENSION pg_trgm`, índice GIN
trigram sobre `normalized_description`). Importación de ~15K filas = payload admin
idempotente con dry-run, **después** del deploy (§1.5). Búsqueda: código exacto/prefijo +
trigram, mínimo de caracteres, límite estricto, cancelación de requests obsoletos; adapta
`Cie10Search.tsx`. Extracción de legado: crea filas en `nota_diagnosticos` apuntando a la
nota, **sin tocar la nota** (§1.1); conserva `diagnostico_cie10` como evidencia.

### Bloque B — Consentimientos (Fases 4–6)

**Fase 4** migra el `dict TEMPLATES` a `consentimiento_plantilla_versiones` v1.0 vía payload
admin. Los endpoints leen del nuevo modelo con **fallback al diccionario** hasta validar
prod. Aceptación dura: los 5 consentimientos actuales emiten contenido **byte a byte
idéntico** bajo el nuevo motor.

**Fase 5** agrega firmantes/testigos/revocación + documento final S3 único. Punto crítico:
si se agrega trigger de inmutabilidad para consentimientos firmados (espejo del de notas),
**diseñarlo desde el inicio para permitir el UPDATE de `verification_token_id` previo al
bloqueo** — exactamente el bug que causó el 500 en `firmar` de notas. La revocación es
registro relacionado nuevo; el original nunca recibe UPDATE.

### Bloque C — Confianza y confiabilidad (Fases 9–11): bloqueo de lanzamiento general

Fase 9 (seguridad/evidencia legal) arranca en **paralelo** desde la semana 1 porque bloquea
venta: rotar secretos, MFA + reauth para firma/exportación, validación completa de JWT de
Clerk (`iss/aud/azp/kid/exp/alg`), threat model del flujo firma→S3→verificación, SAST +
secret scanning + SBOM en CI, pentest antes de clientes de pago. Fases 10–11 (restore drills
trimestrales, E2E Playwright que bloquean deploy) cierran antes del lanzamiento general.

### Bloque D — Diferenciación clínica y adopción (Fases 12–13)

Aquí es donde "cualquier doctor lo quiere": banner de identidad de paciente, alergias/
problemas/medicamentos estructurados longitudinales, addenda firmada, bloqueo optimista
(ETag) e Idempotency-Key en firma/creación de encuentro. Fase 13 hace **excelente** un
flujo de especialidad (dermatología/estética, el ICP actual): plantillas configurables,
favoritos, autosave **de servidor** cada 10–15 s (retirar la promesa offline/localStorage
hasta tener diseño cifrado). Meta medible: −30% tiempo mediano de documentación con 5–10
médicos piloto, ≥80% notas firmadas el mismo día.

---

## 4. Cómo se decide "primer nivel" (no es cantidad de features)

Del §19–§20: el producto es de primer nivel cuando cumple P0 de seguridad/confiabilidad,
hace excelente el flujo diario de UNA especialidad, ofrece salida segura de datos y demuestra
retención real — **no** cuando tiene las 16 fases. Métrica norte: *consultas completadas y
firmadas por médico activo por semana*, con tiempo mediano de abrir-a-firmar. Criterios de
PMF inicial (§19.3): 5–10 médicos del mismo segmento, ≥4 semanas de uso, ≥70% activos a
semana 8, ≥80% firmadas mismo día. Si no se cumple, se pausa expansión y se corrige el flujo
principal antes de agregar features.

## 5. Cumplimiento como evidencia, no como afirmación (§14)

- Nunca se publica "cumple NOM-004/NOM-024" por autoevaluación; se usa "diseñado para apoyar
  el cumplimiento" hasta tener revisión formal. La palabra "certificado"/"cumple" no aparece
  sin evidencia (Definición global de terminado, §11).
- La `docs/compliance_matrix.md` (aparece como borrada en el working tree — **restaurarla**)
  se mantiene viva con estados `no evaluado/parcial/implementado/verificado independiente`.
  Se elimina el estado binario "Cumple ✅".
- Cada fase que agrega evidencia técnica (hash, firma, versión, identidad, bitácora
  inmutable de accesos/exportaciones) actualiza la matriz **antes** que el código (§21: la
  norma prevalece; se actualiza matriz/ADR primero).
- Revisión normativa trimestral y extraordinaria si el DOF publica cambios.

---

## 6. Riesgos principales y su mitigación

| Riesgo | Mitigación en este plan |
|---|---|
| UPDATE accidental a nota/consentimiento firmado (bug 500/CORS) | Regla de diseño §1.1 + regresión `firmar` en CI tras cada fase que toque esas tablas |
| Tabla nueva sin RLS → fuga cross-tenant | `verify_rls.py` acumulativo, corre en CI y en prod post-deploy; bloquea la fase |
| Migración rompe prod sin staging | Job CI con migración real + snapshot pre-deploy + restore ensayado (Fase 0) |
| `release-cedula`/onboarding rompe al cambiar modelo de cédula | `tenants.cedula` sincronizada en la misma fase; workflow probado contra nuevo modelo |
| Importación CIE-10/plantillas corrompe datos | Payload admin idempotente, dry-run, conteos; nunca dentro de Alembic ni desde local |
| Costo se sale de USD 150 | Budget + anomaly detection (Fase 0); cada PR de Terraform con diff estimado; NAT medido antes de tocar |
| Construir features que nadie usa | Cada fase detrás de flag, con métrica de adopción; PMF antes de expandir especialidad |

---

## 7. Qué hacer primero (esta semana)

1. **Fase 0 completa** — es barata y desbloquea todo: job CI de migración real, contrato
   `verify_*`, snapshot + restore ensayado, budget/alertas/tags, S3 Gateway Endpoint.
2. **Restaurar `docs/compliance_matrix.md`** (está borrada en el working tree) y pasarla al
   formato de matriz viva del §14.1.
3. **Arrancar Fase 1** (menor riesgo: solo tablas nuevas) **y** Fase 9 en paralelo (bloqueo
   de venta).

Cada entrega sale detrás de flag, se mide, y puede detenerse. No se ejecuta el plan como
proyecto monolítico.
