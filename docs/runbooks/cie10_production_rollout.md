# Runbook — Rollout CIE-10 en producción

Este procedimiento carga el catálogo CIE-10 completo y extrae, de forma create-only, los
diagnósticos que todavía viven en `notas.diagnostico_cie10`. No reescribe notas históricas.

## Precondiciones

- La rama con `ops-cie10.yml` fue integrada a `main` y el deploy de `main` terminó verde.
- La migración Fase 3 está en `head` en producción.
- El workflow se ejecuta desde `main`; no se admite otra referencia.
- Todo modo `apply` requiere escribir `APLICAR_CIE10_PROD`; los dry-run siguen siendo
  ejecutables sin esa confirmación.
- No debe existir otro rollout CIE-10 activo. El grupo de concurrencia
  `cie10-production` serializa las ejecuciones.

## Ejecución recomendada

1. Abrir **Actions → Ops — CIE-10 Catalog (Production) → Run workflow**.
2. Seleccionar la rama `main`.
3. Elegir `production_rollout`.
4. Escribir exactamente `APLICAR_CIE10_PROD` en `confirm_production`.
5. Ejecutar y conservar el resumen del job como evidencia operativa.

El modo `production_rollout` realiza, en orden y con fail-fast:

1. Crea un snapshot manual de `medrecord-prod` y espera estado `available`.
2. Ejecuta `import_cie10=dry-run` y exige al menos 10 000 filas en el artefacto.
3. Ejecuta `import_cie10=apply` y después `verify=cie10`.
4. Ejecuta `extract_legacy_diagnosticos=dry-run` y valida la consistencia de los conteos.
5. Ejecuta `extract_legacy_diagnosticos=apply` y una verificación CIE-10 final.

Cada paso falla el workflow si el Lambda no responde `statusCode=200`, si `body.ok` no es
`true` o si sus invariantes de conteo no se cumplen. Los resultados contienen únicamente
conteos agregados, no PHI.

## Evidencia y rollback

El resumen de GitHub Actions registra el ID/ARN del snapshot y los conteos de cada fase.
Si una operación falla, no se continúa con la siguiente. El importador es idempotente y la
extracción omite notas que ya tengan diagnósticos estructurados, por lo que el workflow se
puede reintentar después de corregir la causa.

No se debe restaurar automáticamente el snapshot: restaurar RDS es una decisión de
incidente que requiere evaluar los datos escritos después del snapshot. El snapshot
`medrecord-prod-pre-cie10-<run>-<attempt>` es el punto de recuperación y debe conservarse
durante la ventana de observación posterior al rollout.

## Validación funcional posterior

- Buscar por código con y sin punto, por ejemplo `E119` y `E11.9`.
- Buscar descripciones con y sin acentos.
- Crear una nota con dos diagnósticos, exactamente uno principal, y firmarla.
- Confirmar que ambos diagnósticos aparecen en expediente y documento legal imprimible.
- Ejecutar **Ops — Verify (Production)** con `action=cie10` como evidencia independiente.
