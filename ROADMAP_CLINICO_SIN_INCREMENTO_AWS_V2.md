# Roadmap clínico y de producto dentro de USD 150/mes — V2 ampliado

> Sustituye a `ROADMAP_CLINICO_SIN_INCREMENTO_AWS.md`. Esta versión incorpora las
> restricciones reales del código en producción: triggers de inmutabilidad, RLS forzado,
> unicidad de cédula en `tenants`, tooling de operaciones vía Lambda, y la ausencia de
> ambiente de staging. Además amplía el alcance para que el producto sea seguro,
> confiable, clínicamente útil y deseable para médicos, con un techo operativo de
> **USD 150 mensuales**. Las diferencias contra la V1 están marcadas con
> **[CORRECCIÓN]** y las ampliaciones de producto con **[NUEVO]**.

## 0. Resumen de viabilidad

- **Viable dentro de USD 150/mes.** Las Fases 0–8 siguen sin requerir subir la clase de
  RDS, el almacenamiento base ni la memoria/timeout de Lambda. Las fases nuevas pueden
  agregar o sustituir recursos únicamente cuando exista una mejora medible de seguridad,
  confiabilidad o costo y el presupuesto total siga dentro del techo.
- **El almacenamiento ya tiene autoescalado.** `terraform/modules/database/main.tf` define
  `allocated_storage = 20` y `max_allocated_storage = 100` (gp3). El catálogo CIE-10
  completo (~14,000–15,000 filas) ocupa menos de ~30 MB con índices. **[CORRECCIÓN]** La V1
  pedía "medir si cabe"; la respuesta ya es sí, con margen de dos órdenes de magnitud.
- **El patrón de snapshot ya existe.** `notas` y `consentimientos` ya guardan
  `medico_nombre`, `medico_cedula` y `medico_especialidad` al firmar. El constraint
  `notas_tipo_nota_check` ya incluye `historia_clinica` y `evolucion`; la Fase 2 no
  requiere modificarlo.
- **Riesgo técnico principal:** no es capacidad, son los triggers de inmutabilidad, RLS,
  recuperación no ensayada y autorización todavía centrada en un solo usuario. Ver §1 y
  §12–§18.
- **Riesgo de producto principal:** construir muchas funciones sin demostrar que reducen
  tiempo de consulta, errores o trabajo administrativo. Cada función nueva necesita una
  métrica de adopción y una hipótesis validada con médicos del segmento inicial.

## 1. Restricciones del código real que gobiernan todo el plan

Estas cinco restricciones no estaban en la V1 y cambian el diseño de las migraciones.

### 1.1 El trigger de notas firmadas bloquea cualquier backfill sobre `notas`

`notas_signed_immutable` (migración `a1b2c3d4e5f6`) lanza excepción ante **cualquier**
UPDATE cuando `es_editable = false`. Esto incluye agregar `encuentro_clinico_id` o
extraer diagnósticos hacia notas históricas firmadas. Es la misma trampa que causó el
incidente del 500 en `/notas/{id}/firmar` disfrazado de error CORS.

**Regla de diseño:** las notas firmadas nunca reciben UPDATE. Toda relación nueva vive en
tablas hijas o laterales:

- `nota_diagnosticos.nota_id` → apunta hacia la nota; la nota no cambia.
- La relación nota↔encuentro se guarda del lado del encuentro (o en tabla puente), no
  como columna nueva poblada en `notas` para filas históricas. La columna
  `encuentro_clinico_id` en `notas` es válida solo para notas **nuevas** (se escribe al
  crear, antes de firmar).
- Prohibido `ALTER TABLE notas DISABLE TRIGGER` en migraciones salvo decisión explícita
  documentada y con respaldo previo.

### 1.2 Toda tabla nueva con `tenant_id` necesita RLS explícito

El patrón existente (migración `a1b2c3d4e5f6`): `ENABLE ROW LEVEL SECURITY` + `FORCE` +
política `tenant_isolation_<tabla>` con `USING` y `WITH CHECK` sobre
`current_setting('app.current_tenant')::uuid`, más `REVOKE DELETE` para tablas clínicas.

Aplica a: `medicos`, `medico_credenciales`, `encuentros_clinicos`, `nota_diagnosticos`,
`consentimiento_plantillas` y `consentimiento_plantilla_versiones` (si son por tenant).

Dos sutilezas:

- `nota_diagnosticos` **debe llevar su propia columna `tenant_id`**; RLS no puede seguir
  el FK hacia `notas`.
- El catálogo CIE-10 es dato de referencia compartido: **no debe tener política de
  tenant**. Con `FORCE RLS` y sin política devolvería cero filas para todos. Se queda sin
  RLS (solo SELECT para `medrecord_app`, ya cubierto por los default privileges).

Cada fase que agregue tablas actualiza `backend/scripts/verify_rls.py`.

### 1.3 `tenants.cedula` es UNIQUE y hay operación montada encima

La unicidad de `tenants.cedula` sostiene el check de onboarding ("cédula ya registrada")
y el workflow de operaciones `release-cedula.yml` / `backend/scripts/release_cedula.py`.

**Regla de transición (Fase 1):** durante la ventana de doble escritura,
`tenants.cedula` = número de la credencial predeterminada, siempre sincronizados. El
script `release_cedula` se actualiza **en la misma fase**, no después. Los campos de
`tenants` se retiran solo en una versión posterior, tras validar producción.

### 1.4 Los tests verdes no validan migraciones

La suite usa `create_all`, no migraciones Alembic: triggers, políticas RLS y backfills
quedan fuera de lo que los tests pueden atrapar. No hay staging (decisión ya tomada).
Por lo tanto, **cada fase con migración** requiere:

1. El job de CI de verificación de migraciones (patrón del rollout de clinical files).
2. Un payload `verify_*` en el Lambda de administración para verificar en producción
   (patrón `verify_file_storage`).
3. Snapshot de RDS antes de cualquier migración que toque datos (es instancia RDS plana,
   no Aurora).

### 1.5 Importaciones de datos: nunca dentro de Alembic, nunca desde máquina local

Alembic crea **esquema solamente**. La importación CIE-10 (~15K filas) y la importación
de plantillas de consentimiento corren como payload del Lambda administrativo vía
workflow de GitHub (patrón `upgrade_tenant` / `release_cedula`), **después** del deploy —
no durante la ventana de página de mantenimiento. La "herramienta local de contenido" de
la V1 valida y previsualiza localmente, pero la importación siempre entra por el payload
administrativo.

## 2. Objetivo de costo y regla de inversión

El límite operativo es **USD 150/mes para producción**, antes de impuestos y sin incluir
horas de desarrollo. La envolvente será **AWS ≤USD 135** y proveedores SaaS
indispensables ≤USD 15; el objetivo normal será USD 90–125 totales, dejando reserva para
picos, restauraciones y crecimiento. Los SaaS se registran en el mismo tablero para evitar
que el costo total quede oculto fuera de AWS.

### 2.1 Guardas obligatorias

- AWS Budget con alertas reales y pronosticadas al llegar a USD 110, 130 y 145.
- AWS Cost Anomaly Detection y revisión semanal durante piloto, mensual después.
- Etiquetas `Project`, `Environment`, `Owner` y `CostCenter` en todo recurso facturable.
- Cada PR de Terraform incluye diferencia estimada mensual y justificación.
- Ninguna optimización puede reducir aislamiento, cifrado, backups o capacidad de
  recuperación para ahorrar unos dólares.
- Un recurso nuevo se acepta sólo si: resuelve un riesgo o SLO concreto, es la opción más
  simple, tiene dueño/runbook y mantiene el peor caso mensual por debajo de USD 150.
- Toda estimación se valida en AWS Pricing Calculator antes de `apply`; los importes de
  este documento son rangos de planeación, no cotizaciones.

### 2.2 Presupuesto de referencia basado en la infraestructura real

| Grupo | Configuración actual/objetivo | Rango mensual USD |
|---|---|---:|
| RDS PostgreSQL | `db.t4g.small`, Single-AZ inicialmente, 20 GB gp3 | 28–35 |
| Red | 1 NAT Gateway + 1 IPv4 pública; tráfico bajo | 36–40 |
| WAF | 1 Web ACL, reglas administradas y rate limit | 9–12 |
| KMS y Secrets Manager | 2 llaves KMS y secretos activos | 3–5 |
| S3 y protección de archivos | buckets actuales, versiones, lifecycle, escaneo bajo demanda | 3–8 |
| Lambda, API Gateway y CloudFront | carga de piloto/primeros clientes | 2–8 |
| Logs, alarmas, CloudTrail, Route 53, SES, SNS y SQS | baja cardinalidad y retención controlada | 6–12 |
| Reserva operativa AWS | restauraciones puntuales, picos y variación | 3–10 |
| **Envolvente objetivo AWS** | sin asumir free tier | **90–130** |
| SaaS indispensable | Clerk u otro proveedor aprobado | **0–15** |
| **Total operativo objetivo** | margen restante ≥USD 5 | **90–145** |

No se contabiliza RDS Proxy porque **no existe en Terraform**. Tampoco se usa Aurora o
Cognito en la estimación: el código real usa RDS PostgreSQL y Clerk. Si Clerk deja de
estar incluido en su nivel contratado, debe caber en la envolvente SaaS; de lo contrario
se optimiza o se aprueba explícitamente un nuevo límite antes de contratar.

### 2.3 Reglas clínicas de costo que se conservan

- Un solo objeto S3 final por documento y una firma KMS por documento final.
- Borradores en PostgreSQL; no almacenar vistas previas ni copias repetidas.
- El autoescalado gp3 20→100 GB ya existe, pero una alarma debe avisar antes de 70/85%.
- No agregar Redis, OpenSearch, Kubernetes, microservicios, data lake o un segundo motor
  de datos mientras PostgreSQL y el monolito modular satisfagan los SLO.

## 3. Decisiones técnicas cerradas (antes abiertas en V1)

| Tema | Decisión |
|---|---|
| Búsqueda sin acentos | Columna `normalized_description` poblada en la importación (minúsculas, sin acentos, normalizada en Python) + `CREATE EXTENSION pg_trgm` (disponible en RDS PG 15, cero infra) + índice GIN trigram. **No** usar `unaccent()` en expresiones de índice (no es immutable). |
| Tabla CIE-10 | Extender la tabla `cie10` existente en el mismo lugar (PK sigue siendo `code`). No crear tabla paralela. |
| Regla de primera vez | Índice único parcial: `UNIQUE (tenant_id, paciente_id) WHERE tipo = 'primera_vez' AND estado = 'completado'`. A prueba de carreras y más barato que validación transaccional manual (que se mantiene solo para dar error legible). |
| Relación nota↔encuentro | `notas.encuentro_clinico_id` nullable, escrito **solo al crear** notas nuevas. Notas históricas quedan sin encuentro (§1.1). |
| Feature flags | Variables de entorno del Lambda + gating por plan ya existente en `app/core/plans.py`. No construir infraestructura de flags. |
| S3 para consentimiento final | Reusar el bucket de archivos clínicos existente. Ya está resuelto el fix SigV4 para presigned URLs con SSE-KMS. |
| Diagnóstico legado | `notas.diagnostico_cie10` es texto libre `String(255)`; la extracción de la Fase 3 es best-effort declarado, sin promesa de mapeo completo. |

## 4. Alcance funcional (igual que V1)

1. Primera vez / evolución con encuentros clínicos.
2. CIE-10 completo, versionado, múltiples diagnósticos por nota con snapshot.
3. Consentimientos con plantillas versionadas, firmantes, testigos y revocación
   (NOM-004-SSA3-2012).
4. Entidad `medicos` con múltiples credenciales profesionales.

Fuera de las Fases 0–8: verificación automática RNP, firma electrónica avanzada externa,
interoperabilidad FHIR completa, OpenSearch e IA clínica. **[NUEVO]** El soporte mínimo
para equipos pequeños, exportación portable y un subconjunto FHIR de salida se incorporan
después de estabilizar el núcleo, porque influyen directamente en adopción y confianza.

## 5. Modelo de datos (ajustado)

### 5.1 `medicos` y `medico_credenciales`

Como V1 §6.1–6.2, con adiciones:

- Ambas tablas con `tenant_id`, RLS completo y `REVOKE DELETE` (§1.2).
- Unicidad de credencial: sobre el número **normalizado** por médico. La unicidad global
  de cédula permanece en `tenants.cedula` durante la transición (§1.3).
- Una sola credencial predeterminada activa por médico: índice único parcial
  `UNIQUE (medico_id) WHERE es_predeterminada AND activa`.
- Credencial usada en documentos firmados: se desactiva, nunca se borra.

### 5.2 `encuentros_clinicos`

Como V1 §6.3, con:

- RLS completo.
- Índices por `(tenant_id, paciente_id, estado)` y fecha.
- Índice único parcial de primera vez (§3).
- El encuentro referencia la nota inicial creada; para notas históricas la asociación es
  opcional y solo determinista, marcada `clasificacion_origen = 'migracion'` — pero
  implementada sin UPDATE a notas firmadas (§1.1): si la nota está firmada, el vínculo
  vive solo del lado del encuentro.

### 5.3 CIE-10 y `nota_diagnosticos`

- `cie10` extendida: `normalized_description`, `chapter_code`, `chapter_description`,
  `group_code`, `category_code`, `parent_code`, `selectable`, `active`,
  `catalog_version`, `source`, fechas. Sin RLS (§1.2).
- `nota_diagnosticos`: `id`, `tenant_id` (obligatoria, §1.2), `nota_id`, `cie10_code`,
  `orden`, `es_principal`, `certeza`, `descripcion_snapshot`, `version_snapshot`,
  auditoría. RLS completo, `REVOKE DELETE`.
- Regla: un solo `es_principal = true` por nota (índice único parcial).

### 5.4 Plantillas y consentimiento emitido

Como V1 §6.6–6.7. Las cinco plantillas hardcodeadas en
`backend/app/api/v1/consentimientos.py` (`TEMPLATES`) se migran a
`consentimiento_plantilla_versiones` como versión 1.0. Los consentimientos ya emitidos
**no requieren migración**: ya guardan `template_key`, `version` y
`contenido_renderizado` completo.

## 6. Fases

### Fase 0 — Línea base y guardas (2–3 días)

Como V1, más:

- **[CORRECCIÓN]** Confirmar `pg_trgm` disponible y decidir formato de normalización de
  texto (ya decidido en §3; solo validar en la instancia).
- Snapshot de RDS y prueba de restauración (obligatorio por §1.4, no opcional).
- Definir los payloads `verify_*` que cada fase agregará al Lambda admin.
- Documentar fuente y versión CIE-10 (sin cambio).

**Aceptación:** V1 + payload de verificación definido por fase + snapshot probado.

### Fase 1 — Médicos y credenciales (1–2 semanas)

Datos: como V1, con RLS/unicidades de §5.1. La migración de backfill (un `medico` + una
credencial predeterminada por tenant) toca **solo tablas nuevas** — cero riesgo de
triggers.

Backend: como V1. La superficie que lee `tenant.cedula/nombre_medico/especialidad` es
pequeña y conocida: `consentimientos._render_content`, `notas.firmar_nota` /
`_build_legal_note_payload`, `recetas._build_receta_print_payload` (~30 sitios en
total). Se introduce un adaptador único (p. ej. `get_credencial_para_firma(tenant)`) y
los tres flujos lo consumen.

**[CORRECCIÓN]** En esta misma fase: actualizar `release_cedula.py` y el workflow
`release-cedula.yml`, y mantener `tenants.cedula` sincronizada con la credencial
predeterminada (§1.3).

**Aceptación:** V1 + `verify_medicos` en Lambda admin pasa en prod + workflow
release-cedula probado contra el nuevo modelo.

### Fase 2 — Encuentros y primera vez/evolución (1–2 semanas)

Como V1, con:

- **[CORRECCIÓN]** Sin backfill de `encuentro_clinico_id` sobre notas firmadas (§1.1).
- Índice único parcial como enforcement principal de "una sola primera vez" (§3).
- La relación cita→encuentro usa la tabla `citas` existente (`estado`:
  Programada/Cancelada/Completada); citas canceladas jamás generan encuentro.

**Backend + capa de servicio del frontend implementados** (rama `feature/fase2-encuentros`,
ver `WALKTHROUGH_FASE2.md`). El índice parcial solo cubre `estado='completado'`: dos
`primera_vez` pueden coexistir en `programado`/`iniciado` y solo la *finalización* está
guardada. El segundo en completar recibe un **409 estructurado**
(`detail.code = 'primera_vez_duplicada'`, mensaje legible aparte), que el cliente
(`encuentrosApi` + guard `isPrimeraVezConflict`) distingue del 409 terminal de "cancelado"
para tratarlo como **conflicto conciliable** (re-consultar y ofrecer completar como
`subsecuente`). La UI visible (etiqueta primera_vez/subsecuente + precarga historia/evolución,
V1 §7.2) consume esa capa cuando se conecte.

- **[RESUELTO DEUDA FASE 2]** `PATCH /encuentros/{id}/tipo` permite corregir el tipo antes
  de completar, exige `motivo_correccion`, fija `clasificacion_origen='manual'` y registra
  la fecha de actualización. `encuentrosApi.corregirTipo` expone el contrato al cliente y
  la prueba HTTP cubre el ciclo 409 → corregir a `subsecuente` → completar. No toca notas.
  La UI visible general de encuentros sigue dentro de V1 §7.2.

**Aceptación:** V1 + prueba explícita de concurrencia contra el índice parcial +
`verify_encuentros` en prod + 409 estructurado con `code` + guard de conflicto en el cliente.

### Fase 3 — CIE-10 completo y diagnósticos (2 semanas)

- Migración Alembic: solo esquema (extensión de `cie10`, creación de
  `nota_diagnosticos`, extensión `pg_trgm`, índices).
- Importador idempotente como payload del Lambda admin + workflow (§1.5), con reporte de
  conteos y dry-run.
- Búsqueda: código exacto/prefijo + trigram sobre `normalized_description`, mínimo de
  caracteres, límite estricto, paginación, cancelación de requests obsoletos y caché de
  sesión en frontend (el componente `Cie10Search.tsx` existente se adapta).
- Extracción de legado best-effort (§3): crea filas en `nota_diagnosticos` apuntando a la
  nota, **sin tocar la nota** (§1.1). El texto original en `diagnostico_cie10` se
  conserva como evidencia.

**Aceptación:** V1 + importador re-ejecutable sin duplicados + plan de ejecución de la
búsqueda revisado con el catálogo completo + `verify_cie10` en prod.

- **[RESUELTO DEUDA FASE 3]** El editor permite seleccionar múltiples diagnósticos,
  elegir el principal, indicar certeza y retirar elementos antes de crear la nota. Envía
  `NotaCreate.diagnosticos_cie10`, conserva el principal en el snapshot legado y muestra
  la lista estructurada al leer la nota. Los snapshots también quedan dentro del JSON
  canónico que cubre la firma y se imprimen en el documento legal con código, descripción,
  certeza y marca de principal.
- **[CORRECCIÓN OPERATIVA FASE 3]** El deploy de la migración no importa datos por diseño.
  Se agregó `ops-cie10.yml` para `dry-run/apply` del catálogo y extracción de legado, con
  aprobación de `production` y `verify_cie10` automático después de cada `apply`. El modo
  `production_rollout` encadena snapshot RDS → import dry-run/apply → extracción legacy
  dry-run/apply, con confirmación explícita, invariantes de conteo y evidencia del job. La
  API ya no oculta un catálogo incompleto con seis códigos estáticos: devuelve 503
  estructurado `cie10_catalog_not_ready` hasta que haya al menos 10 000 filas activas.
- **[DEUDA FASE 3]** `cie10.catalog_version` es hoy una constante (`CIE-10-MX`) sellada por
  el importador; una tabla de release del catálogo versionada se aborda con el retiro de
  campos legados (Fase 8+). Los diagnósticos ya guardan `version_snapshot`, así que una
  re-versión del catálogo nunca reescribe la historia.

### Fase 4 — Motor de plantillas de consentimiento (2–3 semanas)

Como V1. Las plantillas actuales migran a v1.0 vía payload admin, no vía Alembic (§1.5).
Publicación inmutable por hash; toda corrección es versión nueva. Los endpoints actuales
(`templates`, `create_consentimiento`, `firmar_medico`, etc.) cambian a leer del nuevo
modelo con fallback temporal al diccionario hasta validar producción.

**Aceptación:** V1 + los 5 consentimientos actuales emiten idéntico contenido bajo el
nuevo motor (comparación byte a byte del render) + `verify_plantillas` en prod.

### Fase 5 — Firmantes, testigos, revocación, documento final (1–2 semanas)

Como V1, con:

- Firma KMS única reutilizando `app/services/firma.py` (`sign_note`) y el flujo de
  verification tokens existente.
- Objeto S3 final único en el bucket de archivos clínicos existente (SigV4/SSE-KMS ya
  resuelto). Borradores jamás tocan S3 ni KMS.
- Revocación como registro relacionado; el original no recibe UPDATE (mismo principio
  que §1.1 — considerar trigger de inmutabilidad para consentimientos firmados, espejo
  del de notas, **diseñado desde el inicio para permitir el update del
  verification_token_id previo al bloqueo**, para no repetir el bug de `firmar`).

**Aceptación:** V1 + verificación pública del documento final + prueba de que reimprimir
no genera objetos nuevos.

### Fase 6 — Biblioteca normativa inicial (1–2 semanas, en paralelo)

Igual que V1 (19 plantillas, revisión clínica y jurídica documentada). Solo contenido +
importación por payload admin.

### Fase 7 — Paquetes por especialidad (continua)

Igual que V1. Orden: dermatología/estética primero (coincide con el ICP actual del
producto).

### Fase 8 — Rendimiento, seguridad y despliegue gradual (1 semana)

Como V1, con precisiones:

- Pruebas de carga **locales** (docker-compose ya existe) con catálogo completo y datos
  simulados; en prod solo verificación con payloads.
- Flags por variable de entorno del Lambda en el orden de activación de V1.
- Retiro de campos legados de `tenants` (`cedula`, `especialidad`, snapshot antiguo):
  **última migración del proyecto**, solo tras ≥1 ciclo completo de producción sin
  fallback. Recordar que el deploy pone página de mantenimiento: migraciones largas
  alargan la ventana; todas las migraciones de este plan son DDL rápido + backfills
  chicos, ninguna debería exceder segundos.

## 7. Estrategia de migración de datos (ajustada)

1. **Credenciales:** como V1 §8.1 + sincronía `tenants.cedula` ↔ credencial
   predeterminada durante toda la transición (§1.3).
2. **Encuentros:** como V1 §8.2 + prohibición de UPDATE a notas firmadas (§1.1).
3. **Diagnósticos:** como V1 §8.3; la extracción escribe solo en `nota_diagnosticos`.
4. **Consentimientos:** como V1 §8.4; los emitidos no se re-renderizan nunca.

## 8. Pruebas (ajustada)

Como V1 §9, más:

- **[CORRECCIÓN]** Pruebas de integración que corren las migraciones reales (no
  `create_all`) para triggers, RLS y backfills de cada fase — es la única red de
  seguridad dado §1.4.
- Prueba de regresión específica del flujo `firmar` completo (nota y consentimiento)
  después de cada fase que toque `notas` o `consentimientos`, por el antecedente del
  trigger.
- `verify_rls.py` extendido con cada tabla nueva, ejecutado en prod tras cada deploy.

## 9. Observabilidad, SLO y guardas AWS

La regla de paro de la V1 se mantiene: antes de aumentar capacidad se presentan métricas,
planes de ejecución y optimizaciones intentadas. Se agregan objetivos operativos que
permitan saber si el sistema es confiable en la práctica.

### 9.1 SLO iniciales

| Indicador | Objetivo piloto | Objetivo después de estabilización |
|---|---:|---:|
| Disponibilidad mensual de API clínica | ≥99.5% | ≥99.9% sólo después de habilitar HA comprobada |
| Error 5xx | <1% | <0.5% |
| Latencia API p95 / p99 | <1.5 s / <3 s | <1 s / <2 s en operaciones comunes |
| Guardado de borrador | confirmación <2 s | p95 <1 s |
| RPO de base de datos | ≤5 min | ≤5 min comprobado |
| RTO | ≤4 h Single-AZ | ≤1 h con Multi-AZ y simulacro aprobado |
| Recuperación de documento firmado | 99.9% | 99.99% |

Un SLO no se declara cumplido por configuración; requiere medición y al menos un
simulacro. Si se consume el presupuesto de error mensual, se congelan funciones nuevas y
se prioriza confiabilidad.

### 9.2 Señales y alarmas mínimas

- Correlation/request ID de frontend a API y logs, sin payload clínico.
- Logs JSON con código de error estable, tenant pseudonimizado, duración y resultado.
- Alarmas de Lambda errores/throttles/duración, API 5xx/latencia, DLQ, RDS CPU,
  conexiones, memoria libre, almacenamiento libre y eventos/fallos de failover si se
  habilita Multi-AZ.
- Alarma por fallos de auditoría, firma, KMS, escaneo de archivos y exportación.
- `/health/live` para proceso y `/health/ready` con consulta mínima a PostgreSQL; el
  endpoint público no expone versiones, secretos ni detalles internos.
- Synthetic check de login→lectura segura usando un tenant sintético sin PHI, con
  frecuencia acorde al presupuesto.
- Dashboard único de operación; no introducir una plataforma APM adicional hasta que las
  métricas nativas sean insuficientes.
- Retención explícita por grupo de logs y prohibición automatizada de registrar PHI,
  tokens, firmas manuscritas o documentos completos.

## 10. Estimación y secuencia de valor

- **Núcleo clínico V2 (Fases 0–8): 8–12 semanas.** La Fase 4 sigue siendo la más
  propensa al límite superior.
- **Confianza, seguridad clínica y calidad (Fases 9–11): 6–10 semanas.** Deben comenzar
  antes del lanzamiento general.
- **Experiencia de especialidad y adopción (Fases 12–13): 6–10 semanas**, entregadas en
  incrementos pequeños y validadas con pilotos.
- **Equipos, portabilidad e interoperabilidad mínima (Fases 14–15): 6–10 semanas**, sólo
  cuando la retención de médicos individuales demuestre valor.

Las estimaciones suponen un desarrollador full-stack que conoce el proyecto, más revisión
clínica y jurídica en paralelo. No se deben ejecutar todas las fases como un proyecto
monolítico: cada entrega sale detrás de flag, se mide y puede detenerse.

## 11. Definición global de terminado

Además de la V1 §14:

- Ningún UPDATE se ejecutó jamás sobre una nota firmada; toda corrección es addendum.
- Toda tabla nueva con `tenant_id` aparece en `verify_rls.py` y pasa en producción.
- `release-cedula` y onboarding funcionan contra el modelo de credenciales.
- Todas las importaciones corrieron por el Lambda administrativo con registro del workflow.
- El costo real y pronosticado se mantiene por debajo de USD 150/mes.
- Existe evidencia de restauración completa dentro del RTO/RPO comprometido.
- Los flujos críticos cuentan con E2E automatizado y revisión visual del documento final.
- La matriz normativa fue revisada por responsable jurídico y clínico; el producto no usa
  la palabra “certificado” o “cumple” sin evidencia formal.
- Un médico piloto puede registrar paciente, atender, firmar, recuperar e imprimir sin
  soporte y con una mejora medible de tiempo frente a su proceso anterior.
- El usuario puede exportar sus datos en formato legible y verificable sin depender del
  proveedor.

## 12. Arquitectura objetivo sin over-engineering **[NUEVO]**

Se conserva un **monolito modular**: una SPA, una API Lambda/FastAPI, PostgreSQL, S3 y KMS.
Los límites internos son módulos de dominio y transacciones, no servicios de red.

### 12.1 Regla de simplicidad

No se agregan microservicios, Kubernetes, Redis, OpenSearch, Kafka, una app móvil nativa,
un data lake o un motor propio de feature flags mientras no exista evidencia de que:

1. PostgreSQL/GIN/trigram, Lambda y S3 no cumplen un SLO después de optimizarlos.
2. El problema ocurre con carga real o una prueba representativa.
3. La alternativa simple fue medida y documentada.
4. El costo operativo y cognitivo tiene dueño.

### 12.2 Decisiones permitidas dentro del presupuesto

- **Multi-AZ de RDS:** se habilita cuando el simulacro demuestra que Single-AZ no cumple
  el RTO, al superar 20 médicos de pago, o cuando el producto se use como sistema clínico
  primario durante toda la jornada. Requiere confirmar total ≤USD 150.
- **Entorno efímero de recuperación/preproducción:** restaurar snapshot sólo para probar
  una migración de alto riesgo o simulacro y destruirlo el mismo día. No mantener staging
  completo 24/7 durante el piloto.
- **Reserved DB Instance/Database Savings Plan:** evaluar después de tres meses de consumo
  estable, sin comprometerse antes de conocer la carga.
- **RDS Proxy:** no agregar por costumbre. Sólo si métricas muestran agotamiento de
  conexiones pese a pooling correcto y reutilización del runtime Lambda.

## 13. Optimización de red: NAT Gateway vs VPC endpoints **[NUEVO]**

La sustitución del NAT **no es automáticamente más barata**. En `us-east-1`, un NAT
Gateway tiene costo fijo aproximado de USD 0.045/h más IPv4 y datos; un interface endpoint
se cobra por ENI/AZ/hora y por GB. Cuatro endpoints en dos AZ pueden costar más que el NAT.

### 13.1 Acciones inmediatas de bajo riesgo

1. Agregar **S3 Gateway Endpoint**, sin cargo por hora ni procesamiento, y asociarlo a las
   rutas privadas. Reduce tráfico y costo variable del NAT sin eliminar salida a internet.
2. Medir 30 días de `BytesOutToDestination/BytesInFromSource` del NAT y clasificar destinos.
3. Mantener NAT mientras Lambda necesite llegar a Clerk JWKS u otros endpoints públicos.
4. Restringir egress del security group sólo después de inventariar destinos y probar
   rotación de JWKS, SES, KMS, Secrets Manager y S3.

### 13.2 Matriz de decisión

| Opción | Costo | Seguridad/confiabilidad | Decisión |
|---|---|---|---|
| NAT actual + S3 Gateway Endpoint | fijo ~USD 36–42, menor costo por GB | simple; conserva salida a Clerk | **Recomendada ahora** |
| Interface endpoints en 2 AZ | ~USD 14.60/mes por servicio + datos | privados y redundantes; varios servicios superan NAT | Sólo con cálculo por servicio |
| Interface endpoints en 1 AZ | ~USD 7.30/mes por servicio + datos | más barato pero dependencia zonal | No para todos los flujos críticos |
| NAT instance autogestionada | menor costo posible | parcheo, HA y operación propios | Rechazada por over-engineering/riesgo |
| Eliminar NAT tras cambiar auth | posible | requiere resolver toda salida pública | ADR futuro, no supuesto |

Antes de retirar NAT debe existir una prueba automatizada desde las subredes privadas para
login/JWKS, KMS, Secrets Manager, S3, SES, SQS y cualquier integración externa. El cambio
se despliega con rollback de rutas documentado.

## 14. Cumplimiento mexicano como sistema de evidencia **[NUEVO]**

Marco mínimo a mantener versionado:

- NOM-004-SSA3-2012, del expediente clínico.
- NOM-024-SSA3-2012, sistemas de información de registro electrónico e intercambio.
- Ley Federal de Protección de Datos Personales en Posesión de los Particulares vigente
  (nueva ley de 2025 y reformas posteriores).
- Ley General de Salud vigente y Reglamento en materia de prestación de servicios de
  atención médica.
- Reglas específicas de la especialidad/procedimiento cuando correspondan.

Este roadmap no sustituye dictamen jurídico. “Cumple NOM-004/NOM-024” no se publica por
autoevaluación; se usa “diseñado para apoyar el cumplimiento” hasta contar con revisión o
evaluación formal aplicable.

### 14.1 Matriz viva de cumplimiento

Cada requisito debe registrar: norma/artículo/numeral, interpretación, responsable
(`medico responsable` o `CloudMedRecord encargado`), control técnico, procedimiento
operativo, prueba, evidencia, fecha, versión y riesgo residual. Estados válidos:
`no evaluado`, `parcial`, `implementado`, `verificado independiente`; se elimina el estado
binario “Cumple ✅” sin evidencia.

### 14.2 Funciones legales y de privacidad

- Aviso de privacidad versionado, evidencia de aceptación y registro del texto aceptado.
- Inventario de datos, finalidades, base de tratamiento, transferencias, subencargados y
  ubicación/región de procesamiento.
- Contrato responsable–encargado y cláusulas con AWS, Clerk y proveedores aplicables.
- Flujo ARCO con identidad verificada, folio, plazos, respuesta, bloqueo y excepciones por
  conservación clínica; exportación y rectificación sin alterar documentos firmados.
- Retención mínima clínica calculada desde el último acto médico y política separada para
  logs, borradores, respaldos y documentos finales.
- Incidente/vulneración: clasificación, contención, evaluación de afectación, comunicación,
  evidencia y simulacro semestral.
- Transferencias internacionales y cambios de proveedor sujetos a revisión jurídica.
- Consentimiento explícito cuando legalmente corresponda; nunca confundir consentimiento
  para tratamiento médico con consentimiento para tratamiento de datos.
- Prohibición de usar PHI para analítica, entrenamiento de IA o demostraciones sin base
  jurídica y disociación validada.
- Revisión normativa trimestral y extraordinaria cuando DOF publique cambios.

### 14.3 Evidencia técnica mínima

- Hash, firma, versión, identidad, fecha/hora/zona, credencial y contenido canónico del
  documento final.
- Bitácora inmutable de accesos, exportaciones, firmas, cambios de permisos y operaciones
  administrativas; exportable para auditoría sin exponer más PHI de la necesaria.
- Addenda firmada que referencia al documento original; nunca edición retroactiva.
- Pruebas de confidencialidad, integridad, disponibilidad, autenticación y autorización.
- Conservación y recuperación verificadas, no inferidas desde una regla lifecycle.

## 15. Seguridad, privacidad y confiabilidad de primer nivel **[NUEVO]**

### Fase 9 — Cerrar confianza antes de lanzamiento general (3–5 semanas)

- Rotar todo secreto que haya aparecido en estado/archivos y documentar evidencia.
- Mover secretos de aplicación a Secrets Manager; Lambda recibe ARN, no valor desde
  Terraform/GitHub.
- Validar `iss`, firma, expiración, `aud`/`azp`, algoritmo y `kid` de Clerk; refresco JWKS
  con timeout, caché y fallo seguro.
- MFA obligatorio para propietario, médico y soporte; reautenticación para firma,
  exportación, cambios de credencial y permisos.
- Threat model de los flujos paciente→nota→firma→S3→verificación y archivo→escaneo→descarga.
- OWASP ASVS/API checklist, SAST, secret scanning, dependency/IaC scan y SBOM en CI.
- Pentest independiente antes de clientes de pago y anual/después de cambios críticos.
- Acceso de soporte sin impersonación silenciosa: consentimiento, motivo, expiración y
  auditoría; `break-glass` sólo si se implementa con alerta inmediata.
- Procedimientos de alta/baja de usuarios, pérdida de dispositivo y revocación de sesión.

**Aceptación:** cero críticos/altos explotables abiertos; JWT negativo cubierto; MFA y
reauth E2E; secretos no aparecen en plan/logs; dictamen y pentest con remediación trazable.

### Fase 10 — Recuperación y continuidad clínica (2–3 semanas)

- Restauración trimestral de RDS en entorno efímero y validación funcional de pacientes,
  notas, firmas, tokens, archivos y auditoría.
- Prueba de recuperación de una versión S3 y de verificación de firma después de restaurar.
- Runbooks para RDS, S3, KMS, Clerk, SES, DNS/CloudFront y deploy defectuoso.
- Rollback de Lambda por versión y frontend por versión S3; migraciones expand/contract.
- Modo degradado honesto: si no se puede guardar, bloquear firma y mostrar estado; nunca
  afirmar que se guardó sin confirmación del servidor.
- Formato imprimible de continuidad para que el consultorio registre temporalmente una
  atención durante una caída y la concilie después con autor y hora originales.
- Evaluar el `snapshot_export.tf`: distinguir retención legal de recuperación. Si el
  export no puede restaurar el sistema dentro del RTO o duplica backups sin beneficio,
  retirarlo mediante ADR y conservar la estrategia más simple comprobada.

**Aceptación:** simulacro con RPO/RTO medidos, checklist firmado, evidencia de integridad y
acciones correctivas cerradas.

### Fase 11 — Calidad automatizada y seguridad de cambio (3–5 semanas)

- Tests de frontend con Vitest/Testing Library para validaciones y estados críticos.
- Playwright E2E: onboarding, paciente, cita, encuentro, historia, evolución, CIE-10,
  receta, consentimiento, firma, impresión, verificación, addendum y exportación.
- Pruebas negativas multi-tenant y por rol para cada endpoint.
- Umbral de cobertura por código de negocio nuevo; no premiar cobertura de modelos vacíos.
- Golden files/render visual para documentos médico-legales y zonas horarias.
- Accesibilidad WCAG 2.2 AA en flujos principales, teclado y contraste.
- Concurrencia/idempotencia: doble clic de firma, dos pestañas, request repetido y pérdida
  de respuesta después de commit.
- Carga con datos longitudinales y catálogo completo; límites basados en p95/p99.
- On-demand preprod desde snapshot anonimizado o datos sintéticos para migraciones de alto
  riesgo; destrucción automática el mismo día.

**Aceptación:** los E2E críticos bloquean deploy, rollback ensayado, cero regresiones
visuales legales y presupuesto de pruebas dentro del techo.

## 16. Funciones clínicas que diferencian el producto **[NUEVO]**

### Fase 12 — Seguridad clínica y expediente longitudinal (3–5 semanas)

1. **Banner de identidad:** nombre, edad/fecha de nacimiento, sexo y segundo identificador
   visibles al capturar, recetar y firmar para reducir paciente equivocado.
2. **Alergias estructuradas:** sustancia, reacción, severidad, estado, fuente y fecha;
   alerta en receta y nota. El texto legado se conserva hasta reconciliarlo.
3. **Lista de problemas:** diagnóstico, inicio, estado activo/resuelto, certeza y relación
   con notas, sin modificar snapshots firmados.
4. **Medicamentos longitudinales:** principio/descripcion, presentación, dosis, vía,
   frecuencia, duración, estado y motivo de suspensión; receta sigue siendo snapshot.
5. **Signos vitales tipados:** valor, unidad, fecha y origen; validación de rangos
   físicamente imposibles y confirmación justificada para valores atípicos.
6. **Addenda:** corrección posterior firmada, con motivo y referencia al original.
7. **Bloqueo optimista:** `version`/ETag en borradores para no sobrescribir cambios desde
   dos pestañas; conflicto visible y conciliable.
8. **Idempotency-Key:** crear/finalizar encuentro, firmar nota/receta/consentimiento y
   completar upload no pueden duplicarse por reintentos.
9. **[DEUDA FASE 2]** Poblar `encuentros_clinicos.credencial_id` al firmar la nota del
   encuentro (hoy queda `NULL`, nullable por diseño hasta la firma — §5.2). El vínculo
   viaja del lado del encuentro; la nota firmada nunca recibe UPDATE (§1.1).

No se implementan interacciones farmacológicas o recomendaciones diagnósticas con reglas
caseras. Esas funciones exigen fuente clínica licenciada, responsable editorial, versión,
validación y monitoreo de falsos positivos.

**Aceptación:** pruebas de paciente equivocado, alergia, duplicado, conflicto, addendum e
idempotencia; todo documento final conserva snapshot completo.

### Fase 13 — Flujo excepcional por especialidad (3–5 semanas por paquete inicial)

Segmento inicial: dermatología y medicina estética. Funciones:

Esta fase complementa la Fase 7: la Fase 7 entrega contenido/plantillas; la Fase 13
optimiza la experiencia completa y demuestra su adopción con médicos reales.

- Plantillas configurables de historia, evolución, exploración y procedimiento.
- Favoritos del médico: diagnósticos, planes, indicaciones y recetas, siempre editables.
- Copiar desde consulta previa sólo como borrador, resaltando datos heredados y exigiendo
  confirmación; nunca clonar fechas, signos o exploración sin revisión.
- Atajos de teclado, navegación sin ratón y firma desde tablet responsiva.
- Resumen longitudinal con alergias, problemas, medicamentos, últimas consultas,
  procedimientos, archivos y consentimientos vigentes.
- Fotografías clínicas con consentimiento específico, categoría, lateralidad/zona
  anatómica, fecha y comparación; sin biometría/reconocimiento automático.
- Checklist pre/post procedimiento y seguimiento de eventos adversos.
- Autosave **servidor** cada 10–15 s con estado visible. No guardar PHI en `localStorage`;
  retirar la promesa offline actual hasta tener un diseño cifrado y probado.
- Personalización limitada por configuración JSON versionada; no construir diseñador de
  formularios genérico en esta etapa.

**Aceptación de producto:** con 5–10 médicos piloto, reducir ≥30% el tiempo mediano de
documentación frente a su línea base, ≥80% de notas firmadas el mismo día y cero pérdida
de borradores confirmados por el servidor.

## 17. Equipos, portabilidad y experiencia del paciente **[NUEVO]**

### Fase 14 — Consultorios pequeños y roles mínimos (3–5 semanas)

Modelo simple: `usuarios_tenant`/membresías con roles `propietario`, `medico` y
`recepcion`. La identidad viene de Clerk; pertenencia y permisos se resuelven en backend
desde PostgreSQL, nunca sólo desde el cliente.

- Recepción: agenda y datos administrativos mínimos; sin acceso a notas, diagnósticos,
  recetas, archivos clínicos ni auditoría completa.
- Médico: sólo documentos propios o compartidos por política explícita del consultorio.
- Propietario: usuarios, facturación/plan y auditoría, sin poder alterar documentos.
- Invitación, expiración, baja inmediata y transferencia de propiedad.
- Pruebas de matriz endpoint×rol y auditoría de acceso denegado.
- **[DEUDA FASE 2]** `create_encuentro` hoy resuelve `medico_id` con la heurística "el único
  médico activo del tenant" (`_resolve_medico_id`, LIMIT 1), correcta mientras hay un médico
  por tenant. Al haber varios médicos, el endpoint debe **aceptar `medico_id` explícito** (o
  derivarlo de la membresía del usuario autenticado) y retirar la heurística.

No construir ABAC genérico ni jerarquías hospitalarias. Si una clínica exige permisos más
complejos, se diseña después con casos reales.

### Fase 15 — Importación, salida segura e interoperabilidad mínima (3–5 semanas)

- Importación CSV/XLSX de pacientes con dry-run, deduplicación, reporte por fila y rollback.
- Importación de archivos históricos con manifiesto y clasificación.
- Exportación por paciente y tenant: JSON/CSV legible, PDFs finales, archivos originales,
  auditoría mínima pertinente y manifiesto SHA-256.
- Exportación de paciente síncrona y acotada; exportación completa de tenant mediante
  invocación asíncrona de la Lambda administrativa existente, con estado en PostgreSQL,
  enlace temporal, cifrado y expiración. No reutilizar la DLQ como cola de trabajo ni
  crear otra cola hasta demostrar que el patrón no cumple tiempo/tamaño.
- Exportación FHIR R4 **de salida** limitada inicialmente a Patient, Encounter,
  Condition, Observation, MedicationRequest, DocumentReference y Provenance, validada
  contra perfiles definidos. No anunciar interoperabilidad completa.
- Registro de toda exportación: solicitante, alcance, motivo, fecha, hash y resultado.
- Proceso de terminación de servicio que entrega datos, conserva lo legalmente necesario
  y bloquea/cancela lo restante según dictamen.

**Aceptación:** un tenant puede migrar hacia fuera sin asistencia de ingeniería; el
manifiesto verifica integridad y no expone datos de otro tenant.

### Fase 16 — Experiencia del paciente, sólo después de validar demanda (opcional)

- Enlace de un solo uso para completar datos administrativos y firmar consentimiento.
- Descarga segura de documentos e indicaciones, con expiración y revocación.
- Confirmación/reprogramación de cita y preferencias de comunicación.
- Nada de portal general, mensajería clínica o app móvil hasta demostrar uso suficiente;
  reutilizar SPA/API y verification tokens para evitar otra plataforma.

## 18. AWS Well-Architected aplicado **[NUEVO]**

| Pilar | Decisiones y evidencia requerida |
|---|---|
| Excelencia operativa | IaC, CI/CD, runbooks, owner por alarma, postmortem sin culpa, cambios pequeños y revisión trimestral del roadmap |
| Seguridad | least privilege, RLS, MFA, reauth, cifrado, secretos, threat model, detección, respuesta y pentest |
| Confiabilidad | SLO/error budget, backups, restore drills, idempotencia, rollback, Multi-AZ por gatillo medido |
| Eficiencia de rendimiento | p95/p99, EXPLAIN, paginación, índices, pooling, límites de payload y pruebas de carga |
| Optimización de costos | budget/anomalías, etiquetas, NAT medido, lifecycle, recursos efímeros y cálculo previo a `apply` |
| Sostenibilidad | datos mínimos, lifecycle, evitar duplicados, servicios administrados y capacidad ajustada a demanda |

Se realiza una revisión Well-Architected al cerrar Fase 11 y después semestralmente. Cada
hallazgo tiene severidad, responsable, fecha y decisión; no se crea un proyecto paralelo
de arquitectura.

## 19. Métricas para construir un producto que los médicos quieran **[NUEVO]**

### 19.1 Métrica norte

**Consultas completadas y firmadas correctamente por médico activo por semana**, acompañada
del tiempo mediano desde abrir el expediente hasta firmar. No optimizar clics si aumenta
riesgo clínico.

### 19.2 Embudo y calidad

- Tiempo a primer paciente y primera nota firmada durante onboarding.
- Usuarios activos semanales y retención a 4/8/12 semanas.
- Porcentaje cita→encuentro→nota firmada el mismo día.
- Tiempo mediano/p95 de documentación por especialidad.
- Tasa de borradores abandonados, conflictos, addenda y errores de firma.
- Uso real de plantillas/favoritos y campos que los médicos omiten.
- Tickets por 100 consultas, tiempo de primera respuesta y resolución.
- Satisfacción posterior a tareas concretas; entrevistas mensuales, no sólo NPS.

La telemetría de producto usa IDs pseudónimos y eventos mínimos; nunca diagnóstico,
nombre, contenido de nota, medicamento o PHI. La analítica agregada vive inicialmente en
PostgreSQL/reportes bajo demanda; no se agrega plataforma de analytics sin necesidad.

### 19.3 Criterios de product-market fit inicial

- 5–10 médicos del mismo segmento completan ≥4 semanas de uso real.
- ≥70% continúan activos a semana 8.
- ≥80% de las atenciones creadas terminan firmadas el mismo día.
- Reducción mediana ≥30% en documentación o evidencia equivalente de valor.
- Al menos 3 pilotos aceptarían pagar y recomendar el producto sin una función pendiente
  crítica.

Si no se cumplen, se pausa expansión a otra especialidad y se corrige el flujo principal.

## 20. Orden ejecutivo de implementación **[NUEVO]**

1. Fases 0–3: identidad profesional, encuentros y diagnósticos normalizados.
2. En paralelo, Fase 9: seguridad y evidencia legal; es bloqueo de venta.
3. Fases 4–6: consentimientos y biblioteca revisada.
4. Fases 10–11: restauración, E2E y operación confiable; bloqueo de lanzamiento general.
5. Fases 12–13: seguridad clínica y paquete dermatología/estética; motor de adopción.
6. Fase 7: más paquetes sólo según demanda observada.
7. Fases 14–15: equipos y portabilidad cuando el producto individual retenga usuarios.
8. Fase 16: paciente/portal únicamente con evidencia de uso y presupuesto.

La entrega considerada “primer nivel” no es la que contiene todas las fases, sino la que
cumple P0 de seguridad/confiabilidad, hace excelente el flujo diario de una especialidad,
ofrece salida segura de datos y demuestra retención real.

## 21. Fuentes normativas y técnicas de referencia **[NUEVO]**

Revisadas el 11 de julio de 2026. Deben verificarse nuevamente antes de cada dictamen o
cambio mayor:

- [NOM-004-SSA3-2012, del expediente clínico — DOF](https://www.dof.gob.mx/normasOficiales/4909/SALUD/SALUD.html)
- [NOM-024-SSA3-2012 — DOF](https://www.dof.gob.mx/nota_detalle.php?codigo=5280847&fecha=30/11/2012)
- [LFPDPPP vigente — Cámara de Diputados](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf)
- [Ley General de Salud vigente — Cámara de Diputados](https://www.diputados.gob.mx/LeyesBiblio/pdf/LGS.pdf)
- [Reglamentos federales vigentes — Cámara de Diputados](https://www.diputados.gob.mx/LeyesBiblio/regla.htm)
- [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- [Amazon VPC pricing: NAT Gateway](https://aws.amazon.com/vpc/pricing/)
- [AWS PrivateLink pricing: interface endpoints](https://aws.amazon.com/privatelink/pricing/)
- [Amazon RDS for PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/)
- [AWS Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/)

Las fuentes oficiales prevalecen sobre este roadmap. Si una norma, ley, precio o servicio
cambia, se actualiza primero la matriz/ADR y después la implementación.
