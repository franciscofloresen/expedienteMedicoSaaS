# Runbook — Retención de 5 años y recuperación de la base de datos (NOM-004 §5.14)

> Estado: **implementado en prod (2026-07-15)**. `terraform apply` aplicado (PR #117); ensayo de
> restore superado (RTO ~17 min, ver §5.2); Vault Lock compliance finaliza **2026-07-18 01:29 (-06:00)**.
> Corrigió un hallazgo de confiabilidad/cumplimiento verificado el 2026-07-15: el pipeline de export
> de snapshots RDS a S3 (la supuesta red de retención a 5 años) **estaba caído** y nunca había
> funcionado en su forma actual.
>
> Alcance: **solo la base de datos relacional** (RDS PostgreSQL: notas, expedientes, recetas,
> consentimientos, pacientes, medicos…). Los archivos clínicos en S3 (`expedientes` bucket) ya
> tienen versioning + lifecycle sin expiración y **no** requieren cambios.

> ### 🛠️ Qué ya está en el código (esta rama)
>
> - `terraform/modules/database/backup.tf` (nuevo): vault, IAM, plan mensual 1825 d, selección RDS,
>   notificaciones SNS. **`changeable_for_days = 3` viene DESCOMENTADO** → el Vault Lock arranca en
>   modo **compliance** con ventana de enfriamiento de 72 h.
> - `terraform/modules/database/snapshot_export.tf`: **eliminado** (pipeline Parquet muerto).
> - `terraform/modules/observability/main.tf`: `aws_sns_topic_policy` que permite a
>   `backup.amazonaws.com` publicar (reemplaza la policy default, re-otorga a la cuenta dueña para
>   no romper las alarmas CloudWatch existentes).
> - `terraform/main.tf`: se pasa `ops_sns_topic_arn` a `database` y se quitó
>   `depends_on = [module.compute]` de `observability` (rompía un ciclo nuevo).
> - Guardián proactivo: verificador `backups` en `backend/scripts/verify_registry.py`,
>   opción `backups` en `.github/workflows/ops-verify.yml`, permiso IAM read-only en el Lambda y
>   tests en `backend/tests/unit/test_verify_backups.py`.
>
> **⚠️ Consecuencia del apply:** como `changeable_for_days` ya está descomentado y el pipeline viejo
> se elimina, **un solo `terraform apply` crea el vault en compliance (arranca las 72 h), destruye el
> pipeline viejo, y monta todo lo demás**. El lock sigue siendo REVERSIBLE dentro de esas 72 h. Por
> eso el **ensayo de restore (§5.2) debe correrse DENTRO de la ventana de 72 h** tras el apply. Si el
> ensayo falla, revierte el vault dentro de la ventana. Si prefieres separar los pasos, **comenta
> `changeable_for_days` en `backup.tf` antes del apply** para quedarte en gobernanza y descomentarlo
> después del ensayo (secuencia original §6).

---

## 1. El hallazgo (por qué se hace esto)

Verificación read-only contra la cuenta `107759015501` (us-east-1):

| Comprobación | Resultado |
|---|---|
| Bucket de exports vigente `medrecord-rds-snapshots-prod-…` | existe, **0 objetos** |
| Log group `/aws/lambda/rds-snapshot-export-prod` | **no existe** → el Lambda nunca se ha invocado |
| Export tasks históricos | **1 solo** (2-jul), de un snapshot **manual de prueba** |
| Destino de ese export | bucket `…-**production**-…`, **ya no existe** (renombrado a `-prod-`) → el objeto se perdió |
| Snapshots automáticos diarios | **sí ocurren** (03:04 UTC) |
| Regla EventBridge | ENABLED, pero **no dispara** al Lambda en snapshots automáticos |

**Causa raíz:** el patrón de EventBridge (`Message: "Finished DB Instance snapshot"`, `SourceType:
SNAPSHOT`) corresponde a snapshots **manuales**; los **automáticos** emiten otro evento, así que el
Lambda nunca se dispara. Sumado a un renombre de ambiente (`production`→`prod`) que dejó el pipeline
apuntando a un bucket inexistente y sin revalidar. Quedó **código aplicado pero muerto**.

**Consecuencia:** hoy el único respaldo real de la BD es el **PITR de 35 días** de RDS. Más allá de
35 días **no existe copia de la BD**. La retención legal de 5 años de NOM-004 §5.14 para el
expediente estructurado **no se está cumpliendo**. (Los datos no están perdidos —siguen vivos en la
BD, protegidos por `REVOKE DELETE` + triggers— pero no hay red de respaldo de largo plazo.)

Además, hay un problema de diseño de fondo aunque se "arregle" el disparo: **`StartExportTask`
exporta a Parquet para analítica (Athena), no produce un backup restaurable.** No existe un
`restore-from-parquet` de RDS; recuperar implicaría recrear la BD y recargar Parquet a mano. Es
inadecuado para DR.

---

## 2. Requisitos

**NOM-004-SSA3-2012 §5.14 (conservación ≥5 años)** y **NOM-024** (integridad/seguridad del
registro). Traducido a controles técnicos:

1. Copia **durable y restaurable** del expediente conservada **≥5 años**.
2. **Inmutable** (a prueba de borrado/alteración, incluso por un administrador) → evidencia de
   conservación.
3. Cifrada en reposo (KMS).
4. **Recuperación probada** (un restore real ejecutado y medido; sin evidencia de restore, el RTO/RPO
   es ficción — PLAN_EJECUCION_V2 §2.4).
5. **Detección de fallos**: no puede volver a morir en silencio.

**AWS Well-Architected** (los pilares que gobiernan la decisión):

- **Reliability (REL9):** respaldar datos, automatizar respaldos, **recuperar periódicamente para
  probar**.
- **Security (SEC08):** proteger datos en reposo (KMS) e **inmutabilidad** (WORM).
- **Operational Excellence:** servicio administrado sobre solución artesanal; observabilidad (alarma
  de fallo).
- **Cost Optimization:** cadencia/retención correctas, snapshots incrementales, sin Lambda a medida
  que se pudra.

---

## 3. Decisión de arquitectura

### Opciones consideradas

| Opción | Restaurable | Inmutable | Silent-fail | Costo | Veredicto |
|---|:--:|:--:|:--:|---|---|
| A. Arreglar el patrón EventBridge del pipeline actual | ❌ (Parquet) | ❌ | alto (bespoke) | muy bajo storage | Descartada: no restaurable, frágil |
| B. Cron→Lambda que exporta el snapshot más reciente | ❌ (Parquet) | ❌ | medio | muy bajo storage | Descartada: no restaurable |
| C. Replicación cross-region de backups automáticos | ✅ | ❌ | bajo | bajo | Solo DR regional, retención máx 35 días → **no cubre 5 años** |
| **D. AWS Backup + Vault Lock (elegida)** | ✅ | ✅ (WORM) | **bajo** (alarma nativa) | bajo (mensual, incremental) | **Óptima** |

### Solución elegida: la más barata *y* óptima

**Separar los dos problemas** (son distintos y mezclarlos encarece):

1. **Recuperación operativa (0–35 días):** se **conserva RDS automated backups + PITR** tal cual
   (`backup_retention_period = 35`). Ya existe, es ~gratis (dentro de la franquicia de backup del
   100% del storage) y da granularidad al segundo. **No se toca.**

2. **Conservación legal (35 días – 5 años):** **AWS Backup** con un plan **mensual retenido 1825
   días**, en un **vault con Vault Lock (modo compliance)** → snapshots reales **restaurables**,
   **inmutables (WORM)**, cifrados KMS, administrados y auditables. Con cadencia **mensual** (no
   diaria) y snapshots **incrementales**, el costo es mínimo y cumple §5.14 (la norma exige conservar
   el registro, no granularidad diaria de 5 años).

3. **Se decomisiona** el pipeline Parquet roto (`snapshot_export.tf`): menos código bespoke que
   mantener y menos superficie.

4. **Alarma anti-fallo-silencioso:** notificaciones de AWS Backup al topic SNS existente
   (`observability.alarms`) en `BACKUP_JOB_FAILED`/`EXPIRED`/`RESTORE_JOB_FAILED`. Esto es lo que
   faltó y permitió que muriera sin que nadie se enterara.

Por qué AWS Backup y no arreglar el pipeline: **restaurable** (Parquet no lo es), **administrado**
(lo bespoke fue justo lo que se rompió), **inmutable nativo** (Vault Lock), **auditable/centralizado**
y con **detección de fallos nativa**. El pequeño sobrecosto de storage vs. Glacier se compensa con
recuperabilidad real y cero mantenimiento.

> **Por qué mensual y no diario para 5 años:** dentro de 35 días ya tienes PITR (granularidad fina).
> Fuera de 35 días, el archivo mensual es el registro legal. No hay hueco: 0–35 días = PITR;
> 35 días–5 años = mensual. Diario-por-5-años multiplicaría el storage sin valor legal adicional.
> (Si se quiere cerrar el peor caso "pérdida no detectada >35 días", ver el knob semanal en §4.4.)

> **Nota de cadencia futura:** RDS/Aurora **no** soporta cold storage tiering en AWS Backup, así que
> el control de costo es la **cadencia mensual + incrementalidad**, no la transición a frío.

---

## 4. Diseño detallado (Terraform)

Todo vive en el módulo `terraform/modules/database`. Se **agrega** `backup.tf` y se **elimina**
`snapshot_export.tf`.

### 4.1 Nueva variable de entrada del módulo

```hcl
# terraform/modules/database/variables.tf (o donde vivan las vars del módulo)
variable "ops_sns_topic_arn" {
  type        = string
  description = "SNS topic de alarmas (observability.alarms) para notificar fallos de backup."
}
```

Y en la raíz, al invocar el módulo `database`, pasar
`ops_sns_topic_arn = module.observability.alarms_topic_arn` (exponer ese output en el módulo
`observability` si aún no existe).

### 4.2 `terraform/modules/database/backup.tf` (nuevo)

```hcl
data "aws_caller_identity" "current" {}

# ── Vault del archivo legal a 5 años (inmutable) ─────────────────────────────
resource "aws_backup_vault" "legal_5yr" {
  name        = "medrecord-legal-5yr-${var.environment}"
  kms_key_arn = var.kms_key_arn
  tags = {
    Project     = "medrecord"
    Environment = var.environment
    Purpose     = "nom004-5yr-retention"
  }
}

# ⚠️ Vault Lock — rollout en DOS pasos (ver §6). PASO 1: gobernanza (sin
# changeable_for_days) para validar. PASO 2: descomentar changeable_for_days para
# pasar a COMPLIANCE (WORM). Una vez transcurrido el periodo, es IRREVERSIBLE:
# no se puede borrar el vault, ni acortar retención, ni borrar recovery points
# antes de tiempo — ni siquiera root.
resource "aws_backup_vault_lock_configuration" "legal_5yr" {
  backup_vault_name  = aws_backup_vault.legal_5yr.name
  min_retention_days = 1825
  # changeable_for_days = 3   # ← descomentar en PASO 2 para lock COMPLIANCE
}

# ── Rol IAM que ejecuta backups y restores ───────────────────────────────────
resource "aws_iam_role" "backup" {
  name = "medrecord-backup-role-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "backup.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "restore" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

# ── Plan de backup ───────────────────────────────────────────────────────────
resource "aws_backup_plan" "medrecord" {
  name = "medrecord-backup-plan-${var.environment}"

  # Regla legal: mensual, retenida 5 años, al vault inmutable (NOM-004 §5.14).
  rule {
    rule_name         = "monthly-5yr-legal"
    target_vault_name = aws_backup_vault.legal_5yr.name
    schedule          = "cron(0 5 1 * ? *)" # 05:00 UTC, día 1 de cada mes
    start_window      = 60
    completion_window = 360
    lifecycle {
      delete_after = 1825 # 5 años (cold_storage_after NO aplica a RDS)
    }
    recovery_point_tags = {
      Project     = "medrecord"
      Environment = var.environment
      Retention   = "nom004-5yr"
    }
  }
}

# ── Selección: la instancia RDS de prod ──────────────────────────────────────
resource "aws_backup_selection" "rds" {
  name         = "medrecord-rds-${var.environment}"
  plan_id      = aws_backup_plan.medrecord.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [aws_db_instance.main.arn]
}

# ── Anti-fallo-silencioso: notificar fallos al SNS de alarmas ────────────────
resource "aws_backup_vault_notifications" "legal_5yr" {
  backup_vault_name = aws_backup_vault.legal_5yr.name
  sns_topic_arn     = var.ops_sns_topic_arn
  backup_vault_events = [
    "BACKUP_JOB_FAILED",
    "BACKUP_JOB_EXPIRED",
    "RESTORE_JOB_FAILED",
  ]
}
```

> El topic SNS necesita una policy que permita a `backup.amazonaws.com` publicar. Si el topic
> `observability.alarms` no lo permite aún, añadir un statement `SNS:Publish` para el servicio
> `backup.amazonaws.com` (condición `aws:SourceAccount = <account_id>`).

### 4.3 Decomisionar el pipeline roto

```bash
git rm terraform/modules/database/snapshot_export.tf
```

Esto elimina el Lambda `rds-snapshot-export`, la regla EventBridge, los roles de export y el bucket
`medrecord-rds-snapshots-*` (tiene `force_destroy = false`; al estar vacío, Terraform lo destruye sin
problema). Verificar en `terraform plan` que solo se destruyen esos recursos.

### 4.4 (Opcional, con knob) Tier intermedio semanal

Si se quiere acotar el peor caso "pérdida no detectada entre 35 días y el próximo mensual", añadir
una segunda `rule` **semanal retenida 90 días** en un vault **sin** lock (barato, incremental):

```hcl
  rule {
    rule_name         = "weekly-90d-operational"
    target_vault_name = aws_backup_vault.legal_5yr.name  # o un vault separado sin lock
    schedule          = "cron(0 5 ? * SUN *)"
    lifecycle { delete_after = 90 }
  }
```

Recomendación: **empezar sin esto** (mensual + PITR bastan y son lo más barato); activarlo solo si el
piloto crece y el RPO de 35+ días incomoda.

### 4.5 (Opcional, diferido) DR regional

Copia cross-region del recovery point mensual (Well-Architected Reliability). Añade storage en la
región DR + transferencia. **Cost-gated → Fase 10.** Snippet de referencia:

```hcl
    copy_action {
      destination_vault_arn = aws_backup_vault.dr_region.arn # vault en otra región
      lifecycle { delete_after = 1825 }
    }
```

---

## 5. Pruebas y validación

Infra no lleva unit tests, pero **la recuperación probada es obligatoria** (§2.4). Tres niveles:

### 5.1 Verificación post-apply (humo)

```bash
# El plan y la selección existen
aws backup get-backup-plan --backup-plan-id <id> --query "BackupPlan.Rules[].[RuleName,Lifecycle]"
aws backup list-backup-selections --backup-plan-id <id>

# El vault existe y (paso 2) está en compliance
aws backup describe-backup-vault --backup-vault-name medrecord-legal-5yr-prod \
  --query "[NumberOfRecoveryPoints,Locked,MinRetentionDays]"
```

Como el plan es mensual, para no esperar al día 1 se dispara un backup on-demand de validación:

```bash
aws backup start-backup-job \
  --backup-vault-name medrecord-legal-5yr-prod \
  --resource-arn <arn-de-la-instancia-rds> \
  --iam-role-arn <arn-del-rol-backup> \
  --lifecycle DeleteAfterDays=1825
# Esperar COMPLETED:
aws backup list-recovery-points-by-backup-vault --backup-vault-name medrecord-legal-5yr-prod \
  --query "RecoveryPoints[].[RecoveryPointArn,Status,CreationDate]"
```

### 5.2 Ensayo de restore real (OBLIGATORIO, §2.4) — el "test" que importa

Sin esto, la retención es teatro. Runbook:

1. Restaurar el recovery point a una instancia **temporal** (nombre distinto, misma VPC/subred de BD):
   ```bash
   aws backup start-restore-job \
     --recovery-point-arn <arn> \
     --iam-role-arn <arn-del-rol-backup> \
     --metadata '{"DBInstanceIdentifier":"medrecord-restore-drill","DBInstanceClass":"db.t4g.small","MultiAZ":"false","StorageType":"gp3"}'
   ```
2. Conectarse a la instancia restaurada y verificar integridad **sin PHI en logs**:
   - `SELECT count(*)` de `pacientes`, `notas`, `expedientes`, `consentimientos`, `recetas`,
     `medicos`, `medico_credenciales` y comparar contra prod (conteos, no contenido).
   - Verificar que una nota firmada conocida conserva `firma_hash_contenido` y valida su firma.
   - Confirmar que RLS/triggers migrados están presentes (reusar el patrón de `verify_rls`).
3. **Medir RTO** (tiempo total restore→disponible) y **RPO** (antigüedad del recovery point).
   Registrarlos contra los SLO del §9.1 del roadmap.
4. **Destruir** la instancia de ensayo:
   ```bash
   aws rds delete-db-instance --db-instance-identifier medrecord-restore-drill \
     --skip-final-snapshot --delete-automated-backups
   ```
5. Guardar evidencia (fecha, RTO/RPO, conteos) en este runbook o en la matriz de cumplimiento.

**Cadencia:** ejecutar el ensayo **una vez ahora** (cierra §2.4) y luego **trimestralmente** (Fase 10).

> #### Evidencia del ensayo — 2026-07-15 (cierra §2.4)
>
> - Backup on-demand `e45d9f3c-44de-437a-bd83-c3f7fb6b1c68` → **COMPLETED** (~4.5 min); recovery point
>   en `medrecord-legal-5yr-prod`.
> - Restore `731d771e-16cc-4c9b-a4c6-6a36c7efd07b` → **COMPLETED**; instancia `medrecord-restore-drill`
>   (subred privada, misma SG que prod) alcanzó `available`. **RTO ≈ 17 min · RPO ≈ 0** (recovery point
>   de minutos). Instancia de ensayo destruida; prod intacta (`deletion_protection=true`).
> - Verificador `backups` (Lambda `medrecord-api-prod`, `verify=backups`) → `ok:true`, 1 recovery point
>   0.0 d; suscripción SNS de alarmas **confirmada** y notificaciones del vault activas.
> - **Diferido al primer ensayo trimestral:** los checks de contenido (conteos vs. prod, `firma_hash_contenido`
>   de una nota firmada, RLS/triggers) — el instante de restore es una instancia en subred privada y no
>   hay jump host; requieren ruta de red al VPC (Lambda efímero en VPC o VPN). Script: `drill_checks.sql`.
> - **Gotchas de `start-restore-job`** (para el próximo ensayo): del metadata de
>   `get-recovery-point-restore-metadata` hay que **quitar `DBSnapshotIdentifier`**, poner **`Port=5432`**
>   (el template devuelve 0) y **quitar `DBName`** (Postgres); además sobreescribir `DBInstanceIdentifier`
>   y `DeletionProtection="false"`.

### 5.3 Guardián anti-regresión (que no vuelva a morir en silencio)

Dos capas, ambas baratas:

- **Reactiva (nativa):** las notificaciones SNS del §4.2 avisan de cualquier `BACKUP_JOB_FAILED`.
- **Proactiva (recomendada):** extender el contrato `verify_*` existente
  (`backend/scripts/verify_registry.py`) con un verificador `backups` que, vía boto3, afirme que
  **existe al menos un recovery point con antigüedad < 40 días** en `medrecord-legal-5yr-prod`
  (read-only, sin PHI). Se corre desde `ops-verify.yml` con `action=backups`. Detecta el modo de
  fallo exacto de este incidente (pipeline vivo en código pero sin producir objetos). Este sí lleva
  un test `@pytest.mark.migration_schema`/unit con boto3 mockeado.

---

## 6. Plan de implementación (por pasos, reversible)

| # | Paso | Reversible | Nota |
|---|---|:--:|---|
| 1 | Exponer `alarms_topic_arn` en `observability` y pasarlo a `database` | ✅ | Wiring |
| 2 | Agregar `backup.tf` **sin** `changeable_for_days` (Vault Lock en gobernanza) | ✅ | `terraform plan` primero |
| 3 | `terraform apply`; disparar backup on-demand (§5.1) | ✅ | Aún reversible |
| 4 | Ejecutar el **ensayo de restore** (§5.2) y registrar RTO/RPO | ✅ | Cierra §2.4 |
| 5 | `git rm snapshot_export.tf`; apply para decomisionar el pipeline roto | ✅ | Verificar el plan destruye solo lo esperado |
| 6 | Agregar verificador `backups` a `verify_registry.py` + `ops-verify.yml` | ✅ | Guardián |
| 7 | **Descomentar `changeable_for_days = 3`** → apply → esperar cooling-off | ❌ **IRREVERSIBLE** | Solo tras validar pasos 3–4 |
| 8 | Actualizar `docs/compliance_matrix.md` §5.14 de `parcial`→`implementado` | ✅ | Con evidencia del ensayo |

> **⚠️ El paso 7 es de una sola vía.** El modo compliance de Vault Lock, tras el cooling-off, no se
> puede deshacer. Hacerlo **solo** cuando el backup on-demand y el ensayo de restore hayan pasado. Si
> hay cualquier duda, quedarse en gobernanza (protege igual contra borrado casual; compliance añade
> la garantía WORM regulatoria).

---

## 7. Costos

Instancia actual: `db.t4g.small`, 20 GB gp3 (autoescala a 100). Piloto pequeño, baja escritura.
Snapshots **incrementales** (solo bloques cambiados) → el costo escala con la **rotación de datos**,
no con el número de snapshots.

| Concepto | Precio (us-east-1) | Estimado ahora | Estimado año 5 (maduro) |
|---|---|---|---|
| AWS Backup — storage de snapshots RDS (warm) | ~$0.095 /GB-mes | ~$0.30–1.00 /mes | ~$3–5 /mes |
| AWS Backup — cargo por backup/restore de RDS | $0 (RDS warm) | $0 | $0 |
| SNS (notificaciones de fallo) | ~$0 (bajo volumen) | ~$0 | ~$0 |
| Ensayo de restore (instancia temporal ~1–2 h) | prorrateo t4g.small | ~$0.05 por ensayo | ~$0.05 |
| **RDS automated backups / PITR 35d** (sin cambio) | franquicia 100% del storage | **~$0** | bajo |
| **Se elimina:** Lambda + EventBridge + bucket export | — | pequeño ahorro | pequeño ahorro |
| **Neto** | | **~$1 /mes** | **~$4–5 /mes** |

Supuestos: crecimiento del expediente de ~3 GB a ~30–40 GB en 5 años; cadencia mensual; datos
mayormente aditivos (baja rotación). Muy dentro de la envolvente de USD 150/mes.

**Controles de costo (Cost Optimization):**
- Cadencia **mensual** para el tier de 5 años (no diaria).
- Snapshots incrementales (nativo).
- Sin Lambda/EventBridge/bucket bespoke que mantener.
- Etiquetas `Project/Environment/Purpose` en el vault → visibilidad en Cost Explorer y el AWS Budget.
- Opción semanal/DR-regional **apagadas por defecto**; se activan solo si un riesgo concreto lo pide.

---

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Vault Lock compliance mal configurado (retención muy larga/costosa, irreversible) | Rollout en 2 pasos; validar en gobernanza; `min_retention_days` exacto (1825); cadencia mensual acota el volumen |
| El backup mensual falla y nadie se entera | Notificaciones SNS nativas + verificador `backups` proactivo (§5.3) |
| Restore no funciona el día que se necesita | Ensayo obligatorio ahora + trimestral; RTO/RPO medidos, no supuestos |
| Pérdida regional (todo en us-east-1) | Copia cross-region opcional (§4.5), cost-gated a Fase 10 |
| Costo crece con los datos | Cadencia mensual + incremental + Budget con alertas ya existentes |
| Se decomisiona el pipeline y se quería la analítica Athena | No hay requisito de analítica; si surge, es un export puntual aparte, no una dependencia de retención |

---

## 9. Mapeo a NOM y Well-Architected

| Requisito | Control en este diseño |
|---|---|
| **NOM-004 §5.14** conservación ≥5 años | Backup mensual retenido 1825 días, restaurable |
| **NOM-004 §5.14** inalterabilidad | Vault Lock **compliance** (WORM): no se borra ni acorta, ni por root |
| **NOM-024** seguridad/integridad del registro | Cifrado KMS del vault; rol IAM de mínimo privilegio; auditable |
| **Well-Architected — Reliability (REL9)** | AWS Backup automatizado + **ensayo de restore** periódico |
| **Well-Architected — Security (SEC08)** | KMS en reposo + inmutabilidad WORM |
| **Well-Architected — Operational Excellence** | Servicio administrado (no bespoke) + alarma de fallo |
| **Well-Architected — Cost Optimization** | Cadencia mensual, incremental, sin infra a medida |

---

## 10. Checklist de aceptación

- [x] `backup.tf` aplicado (PR #117); plan mensual + selección de la instancia RDS visibles.
- [x] Backup on-demand de validación en estado `COMPLETED` con recovery point en el vault.
- [x] **Ensayo de restore ejecutado**; RTO/RPO registrados (§5.2); instancia de ensayo destruida.
- [x] Notificaciones SNS de fallo activas; suscripción de email **confirmada** y vault notifications activas.
- [x] Verificador `backups` en `verify_registry.py` + `action=backups` en `ops-verify.yml`, verde.
- [x] Pipeline Parquet (`snapshot_export.tf`) decomisionado; `terraform plan` limpio.
- [x] Vault Lock en **compliance** aplicado (cooling-off); se vuelve permanente **2026-07-18 01:29 (-06:00)**.
- [x] `docs/compliance_matrix.md` §5.14 actualizado a `implementado` con evidencia del ensayo.
- [ ] Ensayo de restore agendado trimestralmente (Fase 10) — **pendiente**; incluye los checks de contenido diferidos.
