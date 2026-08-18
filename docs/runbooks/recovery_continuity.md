# Runbook — recuperación y continuidad clínica (Fase 10)

**Propietario:** Operaciones/Ingeniería · **Revisión:** trimestral y después de cada
incidente o cambio crítico.

Este runbook cubre restauración de datos, recuperación por subsistema, rollback de
despliegue y el modo degradado honesto. No contiene secretos, ARNs de cuenta ni PHI; los
identificadores concretos viven en Secrets Manager y en la consola, nunca aquí.

Principios que ningún procedimiento puede violar:

- **Nunca afirmar que algo se guardó sin confirmación del servidor.** Si una escritura no
  se puede confirmar, la firma queda bloqueada y la UI muestra estado degradado (ver §7).
- **La evidencia clínica no se borra ni se sobrescribe.** Toda restauración es aditiva o
  va a un entorno efímero; jamás un `DELETE`/`UPDATE` sobre notas, consentimientos o
  firmas en producción.
- **Sin PHI en bitácoras de recuperación.** Se registran IDs, tiempos, hashes y conteos.

---

## 1. RDS — restauración y continuidad

`medrecord-prod` es una instancia RDS PostgreSQL single-AZ (decisión deliberada, §12.2)
con PITR de 35 días y archivo legal mensual de 5 años en el vault
`medrecord-legal-5yr-prod` (AWS Backup + Vault Lock COMPLIANCE).

### 1.1 Point-in-time recovery a entorno efímero (drill trimestral)

1. **Nunca restaurar sobre `medrecord-prod`.** Se restaura a una instancia nueva
   (`medrecord-restore-<fecha>`) para validar y medir RPO/RTO sin tocar producción.
2. `aws rds restore-db-instance-to-point-in-time` con `--source-db-instance-identifier
   medrecord-prod`, `--target-db-instance-identifier medrecord-restore-<fecha>` y
   `--restore-time <ISO-8601>` (o `--use-latest-restorable-time`).
3. Esperar `db-instance-available`; registrar el tiempo transcurrido como **RTO medido**.
4. Ejecutar la validación funcional (§1.3) contra la instancia restaurada.
5. Registrar el delta entre `--restore-time` y el último dato consistente como **RPO
   medido**.
6. Destruir la instancia efímera el mismo día (`delete-db-instance --skip-final-snapshot`)
   salvo que se necesite conservarla como evidencia de un incidente.

### 1.2 Restauración desde el archivo legal de 5 años

Usar sólo cuando PITR (35 días) no alcanza la fecha requerida.

1. `aws backup start-restore-job` con el `RecoveryPointArn` del vault
   `medrecord-legal-5yr-prod` y los metadatos de restauración de RDS.
2. El rol de restauración (`modules/database/backup.tf`) ya tiene los permisos; no ampliar
   permisos ad hoc.
3. Continuar en §1.3. El vault está bajo Vault Lock COMPLIANCE: sus recovery points **no
   se pueden borrar** hasta que expire el lock, ni siquiera por el root de la cuenta.

### 1.3 Validación funcional post-restauración

Sobre la instancia restaurada (no producción), confirmar por conteo y por muestreo
estructural, sin exportar PHI:

- Pacientes, expedientes, notas, recetas, citas, encuentros presentes y con conteos
  coherentes con el momento restaurado.
- Firmas: una nota firmada conserva `firma_digital`, `firma_hash_contenido`,
  `firma_kms_key_id` y `verification_token_id`; `es_editable = false`.
- Verificación de firma: reconstruir el payload canónico y validar la firma ECDSA con la
  llave KMS de firma (§3). Una firma válida tras restaurar prueba integridad extremo a
  extremo.
- Tokens de verificación y auditoría presentes; RLS y triggers de inmutabilidad activos
  (correr `-m migration_schema` contra la instancia si se sospecha drift de esquema).

---

## 2. S3 — recuperación de versiones

Los buckets clínicos (expedientes, consentimientos, auditoría) tienen versionado y
SSE-KMS; el de auditoría además Object Lock. Una sobrescritura o borrado accidental se
recupera por versión, no por restauración total.

1. Identificar el objeto y su historial: `aws s3api list-object-versions --bucket <bucket>
   --prefix <key>`.
2. Recuperar la versión buena copiándola sobre la key con
   `aws s3api copy-object --copy-source "<bucket>/<key>?versionId=<VersionId>"` (crea una
   versión nueva; no destruye el historial).
3. Si el objeto es un documento firmado (consentimiento/nota), **verificar la firma después
   de recuperar** contra el hash y la llave KMS: la recuperación no es válida hasta que la
   firma verifica. El test `tests/unit/test_s3_version_recovery.py` reproduce este
   flujo (recuperar VersionId → verificar firma).
4. Nunca borrar una versión del bucket de auditoría: Object Lock lo impide por diseño.

---

## 3. KMS — llaves de cifrado y de firma

Dos llaves: la de **cifrado** (datos en RDS/S3) y la de **firma** NOM-004 (`Sign/Verify`,
ECDSA P-256). Ambas son administradas por AWS con rotación de material habilitada donde
aplica.

- **Nunca programar el borrado de la llave de firma.** Sin ella no se pueden verificar las
  firmas históricas: sería destrucción de evidencia médico-legal.
- Si se sospecha compromiso, rotar el material y **conservar** la versión anterior para
  verificar firmas emitidas con ella; la verificación selecciona la versión por el
  `firma_kms_key_id` almacenado.
- El acceso a `Sign` está acotado al rol Lambda exacto (Fase 9, Lote 2). Un cambio de rol
  requiere actualizar la política de la llave en el mismo PR de Terraform.
- Pérdida de acceso (no de la llave): revisar la política de la llave y el rol de ejecución
  Lambda; `verify=fase9` confirma la postura de firma sin exponer secretos.

---

## 4. Clerk — autenticación

- El backend falla cerrado: sin validación de JWT (firma, `iss`, `exp`, `kid`, JWKS) no hay
  acceso. Una caída de Clerk bloquea el login, no expone datos.
- Rotación/pérdida de `CLERK_SECRET_KEY` y de sesiones/dispositivos: ver el runbook
  [`security_access_lifecycle.md`](security_access_lifecycle.md). El secreto vive en
  Secrets Manager (`medrecord/prod/app-config-v2`), nunca en variables Terraform ni en
  GitHub.
- Degradación honesta: si el token no valida, la UI pide reautenticación; nunca se asume
  identidad ni se firma sin MFA reciente cuando la política de reauth está activa.

---

## 5. SES — correo de citas

- Identidad `citas.cloudmedrecord.com` con MAIL FROM y DNS **manual** (no Route53). Un
  cambio de DNS mal aplicado rompe DKIM/SPF en silencio.
- El envío ocurre después del commit de la cita y es best-effort: un fallo de SES **no**
  revierte la cita ni bloquea la atención; se registra y se reintenta.
- `SES_SENDER_EMAIL` vacío = no-op silencioso por diseño (entornos sin correo). Verificar
  esta variable antes de diagnosticar "no llegan correos".
- Recuperación: revalidar DKIM/SPF/DMARC en la consola SES y en el DNS del dominio;
  reenviar no reintenta correos pasados, sólo restablece el canal.

---

## 6. DNS / CloudFront — frontend

- El frontend es S3 estático detrás de CloudFront. Un despliegue defectuoso se revierte por
  **versión de objeto S3** (§8), no reconstruyendo.
- Tras revertir, invalidar la caché de CloudFront (`create-invalidation --paths "/*"`) para
  que los clientes reciban el `index.html` correcto.
- El DNS del dominio es manual; un cambio de registro se propaga con TTL. No cambiar
  registros DNS durante un incidente salvo que el incidente sea el DNS.

---

## 7. Modo degradado honesto

Objetivo: durante una caída parcial, **nunca** decirle al médico que algo se guardó cuando
no se confirmó, y **no** permitir firmar sobre datos que no se pueden persistir.

- **Backend.** `get_db` confirma la transacción sólo al salir con éxito del endpoint; la
  respuesta `2xx` se envía únicamente tras un commit durable. Un fallo de commit se
  convierte en `5xx`, nunca en un falso éxito. `/health/ready` hace un round trip a
  PostgreSQL y responde `503` si la base no está disponible. La firma falla cerrada: si KMS
  no responde, devuelve `503 "servicio de firma no disponible"` y la nota queda editable.
- **Señal de estado.** `GET /health/ready` (público, sin PHI, sin auth) hace un round trip
  a PostgreSQL y responde `200`/`503`: es la señal que el cliente sondea para conocer si las
  escrituras se pueden confirmar antes de intentar una acción sensible.
- **Frontend.** El hook `useServerHealth` sondea `/health/ready`; `DegradedModeBanner`
  muestra el estado; el botón de firma se deshabilita en estado degradado. Ninguna vista
  marca "guardado"/"firmado" salvo tras una respuesta `2xx` del servidor.
- **Continuidad en papel.** Si el sistema no puede guardar, el consultorio usa el
  **formato imprimible de continuidad** (`/continuidad`, `ContinuidadImprimible`) para
  registrar la atención con autor y hora originales, y la concilia después. El formato deja
  explícito que es un registro temporal a conciliar, con la hora real de atención.

---

## 8. Rollback de despliegue

Workflow: `.github/workflows/ops-rollback.yml` (manual, environment `production`, OIDC, sin
credenciales persistentes).

- **Lambda (backend) por versión.** El deploy publica versiones inmutables; el rollback
  reapunta el alias/función a la versión previa buena. `dry_run` lista las versiones
  disponibles; `apply` exige confirmación explícita y `main`.
- **Frontend por versión S3.** Se restaura la versión previa del `index.html` (y assets si
  cambiaron) por VersionId y se invalida CloudFront.
- **Migraciones expand/contract.** Las migraciones son aditivas (expand) y separan el
  retiro de columnas (contract) en un paso posterior, de modo que un rollback de Lambda a
  la versión anterior siga siendo compatible con el esquema. **Nunca** hacer contract en el
  mismo deploy que introduce el expand.
- **Página de mantenimiento.** El deploy intercambia `index.html` por `maintenance.html`
  durante la ventana; el job de frontend restaura `index.html` al terminar. Si un deploy
  queda a medias, el rollback de frontend restablece `index.html`.

---

## 9. Checklist del simulacro trimestral (RPO/RTO)

Se archiva firmado por el responsable de la corrida. No incluye PHI.

- [ ] PITR a entorno efímero completado; **RTO medido** registrado.
- [ ] **RPO medido** registrado (delta entre punto restaurado y último dato consistente).
- [ ] Validación funcional §1.3 pasada (conteos + muestreo estructural).
- [ ] Recuperación de una versión S3 y **verificación de firma** tras recuperar.
- [ ] Rollback de Lambda y de frontend ensayado en el entorno de la corrida.
- [ ] Instancia efímera destruida (o conservada como evidencia con justificación).
- [ ] Hallazgos y acciones correctivas abiertas con responsable y fecha; cerradas antes del
      siguiente simulacro.

**Aceptación de fase:** simulacro con RPO/RTO medidos, checklist firmado, evidencia de
integridad (firma válida tras restaurar) y acciones correctivas cerradas.
