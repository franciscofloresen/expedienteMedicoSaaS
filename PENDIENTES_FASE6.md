# Pendientes — Fase 6

> **RESUELTO.** La reordenación del snapshot vive en
> `.github/workflows/ops-consent-templates.yml` (dry-run → snapshot → apply) y el
> workflow de limpieza es `.github/workflows/ops-snapshot-cleanup.yml`. La lógica de
> clasificación (keep_latest, cutoff de antigüedad, protección `Retention=hold`, filtro
> por etiqueta de propósito) quedó verificada. Los criterios abajo se conservan como
> especificación del comportamiento.

## Retención y limpieza de snapshots manuales de rollout

- [x] Mover la creación del snapshot en
  `.github/workflows/ops-consent-templates.yml` para que ocurra después de un dry-run
  exitoso y justo antes del `apply`. Así una publicación rechazada por la compuerta
  clínica/jurídica no genera almacenamiento innecesario.
- [x] Crear un workflow manual de limpieza para snapshots de rollout con estos inputs:
  - `action`: `dry_run` o `delete`;
  - `older_than_days`: 14 por defecto;
  - `keep_latest`: 3 por defecto;
  - `confirm_production`: exigir `ELIMINAR_SNAPSHOTS_ANTIGUOS` para borrar.
- [x] Ejecutar el workflow bajo el environment `production`, con OIDC y aprobación
  humana, sin credenciales AWS persistentes.
- [x] Limitar candidatos a snapshots manuales de `medrecord-prod` etiquetados con
  `Purpose=pre-consent-template-publication`.
- [x] Proteger snapshots con `Retention=hold`, aunque superen la antigüedad configurada.
- [x] Mostrar identificador, fecha, antigüedad y tamaño/costo estimado en el resumen del
  dry-run antes de permitir el borrado.
- [x] No borrar snapshots automáticos de RDS ni recovery points del vault
  `medrecord-legal-5yr-prod` protegido con Vault Lock.
- [x] Después de borrar, registrar en el resumen de GitHub los identificadores eliminados
  y volver a listar los snapshots conservados.

### Política recomendada

- RDS automatizado/PITR: conservar 35 días, como ya define Terraform.
- Archivo legal AWS Backup: mensual y 5 años, como ya define Terraform.
- Snapshot manual previo a rollout: conservar 14 días y, como mínimo, los 3 más
  recientes.
- Excepción: conservar indefinidamente mientras tenga `Retention=hold` por incidente,
  auditoría o investigación abierta.

### Criterios de aceptación

- `dry_run` nunca elimina recursos y enumera exactamente los candidatos.
- `delete` falla sin confirmación, fuera de `main` o sin aprobación de `production`.
- Un snapshot sin la etiqueta de propósito esperada nunca es candidato.
- Los tres snapshots manuales de rollout más recientes permanecen disponibles.
- Los backups automáticos y el archivo legal de cinco años permanecen intactos.
