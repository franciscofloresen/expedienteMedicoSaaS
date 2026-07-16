# Walkthrough — Fase 4: motor versionado de consentimientos

## Resultado

La Fase 4 reemplaza el `dict TEMPLATES` como fuente primaria por un catálogo versionado
en PostgreSQL, sin modificar consentimientos históricos y sin agregar infraestructura
AWS. El diccionario permanece temporalmente como fallback de rollout y sólo se usa si no
existe ninguna versión publicada en base de datos.

## Modelo y garantías

- `consentimiento_plantillas` conserva la identidad estable, categoría, especialidad,
  procedimiento y estado general.
- `consentimiento_plantilla_versiones` conserva nombre, contenido estructurado, campos,
  firmas requeridas, referencias, revisión, estado y hash SHA-256 canónico.
- El catálogo es referencia global, sin `tenant_id` ni RLS. `medrecord_app` sólo tiene
  `SELECT`; la escritura entra por el payload administrativo auditado.
- `uq_plantilla_version_publicada` permite una sola versión publicada por plantilla.
- `consentimiento_plantilla_version_immutable` bloquea cambios o borrado de contenido
  publicado. Una versión publicada sólo puede pasar a `retirada`.
- `consentimientos.plantilla_version_id` se escribe únicamente en emisiones nuevas. Los
  registros históricos conservan `template_key`, `version` y `contenido_renderizado` y
  no reciben backfill.

## Contenido y motor

El artefacto fuente es `backend/app/data/consent_templates.json`. Contiene las cinco
plantillas actuales como v1.0, estructura de campos, firmas y referencia normativa. El
render nuevo conserva exactamente el formato anterior; una prueba congela el renderer
legado y compara los bytes UTF-8 de las cinco salidas.

Herramienta local:

```bash
cd backend
python -m scripts.consent_template_tool validate
python -m scripts.consent_template_tool preview general_atencion
python -m scripts.consent_template_tool compare catalogo-anterior.json catalogo-nuevo.json
```

Para corregir contenido ya publicado se agrega otra versión en el JSON. Reutilizar el
mismo `template_key` + `version` con otro hash hace fallar tanto el dry-run como el apply.

## API

- `GET /api/v1/consentimientos/templates` lee versiones publicadas y acepta filtros
  `especialidad` y `procedimiento`.
- `POST /api/v1/consentimientos` valida los campos declarados por la versión, renderiza de
  forma determinista y guarda el vínculo snapshot `plantilla_version_id`.
- Si el catálogo está totalmente vacío, ambos flujos usan el fallback legado. En cuanto
  hay una publicación, una key ausente o retirada deja de ser válida.

## Operación en producción

El workflow `Ops — Consent Templates (Production)` implementa el rollout controlado:

1. Sólo permite escritura desde `main` con confirmación
   `PUBLICAR_PLANTILLAS_PROD` y aprobación del environment `production`.
2. Crea y espera un snapshot manual de RDS.
3. Invoca `{"import_consent_templates":"dry-run"}` y exige cinco documentos válidos.
4. Invoca `{"import_consent_templates":"apply"}`; el importador es idempotente.
5. Invoca `{"verify":"plantillas"}` y registra snapshot, conteos y resultado en el job.

`verify_plantillas` confirma tablas, permisos de sólo lectura, trigger de inmutabilidad,
una sola versión publicada, hashes exactos de las cinco v1.0 y la columna snapshot. No
lee ni devuelve PHI.

## Evidencia de validación local

- Cadena Alembic completa sobre PostgreSQL 15: verde.
- Round-trip `downgrade -1` → `upgrade head`: verde.
- `verify_rls.py`, incluyendo permisos del catálogo compartido: verde.
- Suite `migration_schema`: 35 pruebas verdes, incluida la regresión completa
  consentimiento → firma paciente → firma médico → verificación pública.
- Suite unitaria: 38 pruebas verdes.
- Ruff y MyPy: verdes.

## Pendiente de despliegue

La implementación está lista para deploy, pero este cambio no ejecuta operaciones en
producción. Después de desplegar la migración debe correrse el workflow de rollout y
conservarse su evidencia. La ampliación a 19 plantillas y su revisión clínica/jurídica
documentada corresponde a la Fase 6.
