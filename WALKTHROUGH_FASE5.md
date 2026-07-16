# Walkthrough — Fase 5: firma final, evidencia y revocación de consentimientos

## Resultado

La Fase 5 completa el ciclo del consentimiento clínico: captura al paciente o su
representante/tutor, exige los testigos declarados por la plantilla, permite elegir la
credencial activa del médico y produce una sola evidencia final firmada. Los borradores
no consumen KMS ni escriben en S3; la impresión y la verificación reutilizan el mismo
documento final.

No se agregó infraestructura AWS. Se reutilizan el bucket clínico existente —con
versionado y cifrado SSE-KMS—, `sign_note` y los tokens públicos de verificación.

## Modelo y garantías

- `consentimiento_firmantes` conserva evidencia inmutable de paciente,
  representante/tutor y testigos: identidad, relación/motivo, orden, fecha, firma
  normalizada y SHA-256.
- `consentimiento_documentos_finales` vincula exactamente un PDF con cada
  consentimiento: bucket, key determinista, VersionId, ETag, hash, tamaño y tipo MIME.
- `consentimiento_revocaciones` registra la revocación de forma lateral. No cambia el
  consentimiento firmado ni reemplaza o elimina su PDF.
- Las tres tablas tienen `tenant_id`, RLS habilitado y forzado, política exacta por
  tenant, `SELECT`/`INSERT` para `medrecord_app`, prohibición de `DELETE` y triggers de
  inmutabilidad.
- El trigger de `consentimientos` bloquea todo cambio posterior a la firma. Su única
  excepción es el enlace legado de un `verification_token_id` faltante, sin permitir
  modificar ningún otro campo; así no se repite la regresión histórica de notas.
- Las claves únicas y el bloqueo `FOR UPDATE` impiden una segunda finalización,
  documento o revocación para el mismo consentimiento.

## Firmas y documento canónico

El componente `SignaturePad` captura mouse, pluma o touch en canvas y exporta JPEG
comprimido. El backend no confía en el cliente: limita el tamaño, decodifica y vuelve a
normalizar PNG/JPEG con Pillow antes de calcular el hash. Se conserva compatibilidad con
la evidencia base64 histórica.

El contenido firmado se construye una sola vez con:

- snapshot de plantilla, contenido renderizado y campos del consentimiento;
- firmantes en orden y hashes de sus firmas;
- snapshot del médico y de la credencial seleccionada;
- expediente, paciente, tenant y timestamps relevantes.

Ese JSON canónico se firma una vez mediante `sign_note`. El PDF final incluye contenido
clínico, firmantes, médico/credencial, hash firmado y QR al verificador público. Sólo
después se guarda bajo la key determinista
`tenants/{tenant_id}/consentimientos/{consentimiento_id}/final.pdf`.

## API y experiencia de usuario

- `GET /api/v1/consentimientos/credenciales-firma` lista credenciales activas del médico.
- `POST /api/v1/consentimientos/{id}/firmar-paciente` recibe paciente o
  representante/tutor y el número exacto de testigos exigido por la versión de plantilla.
- `POST /api/v1/consentimientos/{id}/firmar-medico` selecciona credencial, firma el
  contenido canónico y crea el PDF final una sola vez.
- `GET /api/v1/consentimientos/{id}/print` entrega un URL temporal al mismo VersionId; no
  hace otro `PUT`, no vuelve a firmar y no renderiza un documento alterno.
- `POST /api/v1/consentimientos/{id}/revocar` crea el evento lateral y revoca el token
  público, sin actualizar el original firmado.
- `GET /api/v1/verify/{token}` valida firma/hash y existencia del documento final. Una
  revocación se muestra como tal, sin exponer PHI ni entregar el PDF públicamente.

La pantalla de expediente presenta los firmantes requeridos dinámicamente, valida
relación y motivo para representación, ofrece selector de credencial y distingue
firmado/revocado. La pantalla de impresión abre el PDF almacenado y muestra una alerta
visible si existe revocación.

## Operación segura en producción

Este cambio no ejecuta operaciones en producción. El orden de rollout es:

1. Confirmar backup reciente y crear snapshot manual de RDS.
2. Desplegar en ventana de mantenimiento; Alembic aplica sólo DDL aditivo, sin backfill ni
   `UPDATE` sobre evidencia histórica.
3. El deploy ejecuta y exige el payload `{"verify":"consentimientos"}` antes de retirar
   mantenimiento; ejecutar también `verify_rls.py` en la comprobación acumulativa.
4. Validar un consentimiento controlado de punta a punta: borrador, firmantes, una firma
   médica, una impresión, verificación pública y revocación.
5. Confirmar en métricas/logs que hubo un solo llamado de firma y un solo `PutObject`, y
   que reimpresión/verificación sólo realizaron lecturas.

Ante una falla estructural, detener nuevas firmas y revertir la aplicación antes de
considerar downgrade. La migración es reversible, pero no debe bajarse después de crear
evidencia real sin preservar primero las tablas laterales y objetos S3.

## Evidencia de validación local

- Ruff y MyPy sobre backend: verdes.
- TypeScript, ESLint y build de producción del frontend: verdes.
- Simulación del paquete Lambda: 37,255,084 bytes comprimidos y 124 MB descomprimidos;
  ambos bajo los límites. El workflow ahora falla antes del deploy si los rebasa.
- Suite rápida completa sobre PostgreSQL limpio: 75 pruebas verdes, 34 omitidas.
- Suite con la cadena Alembic real: 37 pruebas verdes.
- Round-trip `upgrade head` → `downgrade -1` → `upgrade head`: verde.
- Pruebas específicas: normalización/compresión, PDF válido, firma y `PutObject` únicos,
  rechazo de segunda finalización, reimpresión del mismo key/VersionId, verificación
  pública, revocación lateral, original byte a byte inalterado, RLS e inmutabilidad.

## Pendiente de despliegue

La implementación está lista para revisión y despliegue controlado; no fue aplicada a
producción. La revisión clínica/jurídica y ampliación a 19 plantillas sigue en Fase 6. La
reauth/MFA, hardening de JWT y threat model integral pertenecen al bloqueo de confianza
de Fase 9 y no deben confundirse con esta entrega funcional.
