# ADR 0001 — Retirar el pipeline de export de snapshots (Parquet a S3)

- **Estado:** Aceptada
- **Fecha:** 2026-08-18
- **Contexto de fase:** Fase 10 — Recuperación y continuidad clínica
- **Decisores:** Ingeniería/Operaciones

## Contexto

El diseño original incluía `snapshot_export.tf`: un pipeline que exportaba snapshots de RDS
a S3 en formato Parquet como estrategia de retención a largo plazo. La Fase 10 exige
distinguir **retención legal** de **recuperación operativa** y evaluar si ese export aporta
capacidad de restauración dentro del RTO o si sólo duplica backups sin beneficio.

Hallazgos de la evaluación:

- El export a Parquet **no puede restaurar el sistema**: produce archivos analíticos, no una
  instancia RDS recuperable. No contribuye al RTO.
- En operación real el pipeline estuvo "vivo en código" pero produjo cero objetos durante
  meses — un modo de fallo silencioso: aparentaba respaldo sin generarlo.
- La retención legal a 5 años ya está cubierta por **AWS Backup + Vault Lock COMPLIANCE**
  (vault `medrecord-legal-5yr-prod`, snapshot mensual restaurable retenido 1825 días), con
  un drill de restauración aprobado (RTO ~17 min). Esa estrategia es restaurable y más
  simple.
- Mantener ambos duplicaba almacenamiento y superficie de mantenimiento sin ningún
  beneficio de recuperación.

## Decisión

Retirar el pipeline de export de snapshots a Parquet. La retención legal y la recuperación
se cubren con:

- **PITR de RDS** (35 días) para recuperación operativa reciente.
- **AWS Backup + Vault Lock COMPLIANCE** (`modules/database/backup.tf`) para el archivo
  legal mensual de 5 años, restaurable y probado.

El recurso `snapshot_export.tf` fue eliminado de Terraform; `modules/database/backup.tf`
documenta el reemplazo en su cabecera. Los procedimientos de restauración viven en
[`docs/runbooks/recovery_continuity.md`](../runbooks/recovery_continuity.md).

## Consecuencias

- **Positivas:** una sola estrategia de respaldo, restaurable y verificada por drill; menos
  almacenamiento y menos superficie de fallo silencioso; separación clara entre retención
  legal (Vault Lock) y recuperación (PITR).
- **Negativas / aceptadas:** se pierde el artefacto analítico en Parquet. No se usaba para
  recuperación y no había consumidor analítico en producción; si en el futuro se necesita
  analítica sobre datos históricos, se diseñará por separado sobre una restauración
  controlada, sin volver a acoplarla a la ruta de respaldo.

## Alternativas consideradas

1. **Conservar el export en paralelo** — rechazada: duplica backups sin aportar RTO y
   reintroduce el modo de fallo silencioso.
2. **Reparar el export para que sí genere objetos** — rechazada: aun funcionando, Parquet no
   restaura el sistema; arreglaría el síntoma (cero objetos) sin dar capacidad de
   recuperación.
