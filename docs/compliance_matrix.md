# Matriz de Cumplimiento Normativo (NOM-004 / NOM-024)

Este documento mapea los requisitos regulatorios mexicanos para Expedientes Clínicos Electrónicos contra la implementación técnica de la plataforma.

## NOM-004-SSA3-2012 (Del Expediente Clínico)

| Sección | Requisito | Implementación Técnica | Estado |
|---------|-----------|------------------------|--------|
| **5.3** | Datos de identificación del paciente | El modelo `Paciente` en PostgreSQL exige `nombre_completo`, `sexo` y `fecha_nacimiento`. El frontend valida formato y obligatoriedad. | Cumple ✅ |
| **5.4** | Historia Clínica Completa | Antecedentes médicos se almacenan como JSONB cifrado con KMS (Envelope Encryption) en la columna `antecedentes_cifrado` de la tabla `expedientes`. | Cumple ✅ |
| **5.8** | Notas Médicas (Fecha, hora, nombre y firma) | Cada registro en `notas_medicas` captura timestamp automático y requiere una firma digital. El nombre y cédula del médico se guardan inmutables en el momento de la firma. | Cumple ✅ |
| **5.14** | Conservación por 5 años | Las eliminaciones de pacientes o notas en la API realizan un "soft delete" (`activo = False`). No existen endpoints de "hard delete" disponibles para la UI clínica. Los datos en S3 migran a Glacier IR pero no expiran antes de 1825 días. | Cumple ✅ |

## NOM-024-SSA3-2012 (Sistemas de Información de Registro Electrónico para la Salud)

| Sección | Requisito | Implementación Técnica | Estado |
|---------|-----------|------------------------|--------|
| **Cifrado** | Datos en reposo y en tránsito | TLS 1.3 forzado (tránsito). Envelope Encryption mediante AWS KMS (CMK + DEK) para la base de datos PostgreSQL en Amazon Aurora. | Cumple ✅ |
| **Firma** | Firma electrónica | Implementación de `firma.py` utilizando criptografía de curva elíptica ECDSA P-256 (estándar NIST). Se firma el hash SHA-256 del contenido canónico de la nota. | Cumple ✅ |
| **Trazabilidad** | Audit Trail inalterable | Middleware de auditoría en FastAPI captura `INSERT`, `UPDATE`, `DELETE`. Base de datos usa triggers a nivel tabla que insertan en `audit_log` con los valores previos y nuevos (`datos_antes`, `datos_despues`). La tabla prohíbe `UPDATE` y `DELETE`. | Cumple ✅ |
| **Control Acceso**| Roles y privilegios | Autenticación basada en JWT asimétrico (AWS Cognito). Aislamiento estricto multi-tenant mediante Row-Level Security (RLS) en PostgreSQL impulsado por el header `X-Tenant-ID`. | Cumple ✅ |
| **Integridad** | Detección de alteraciones | El endpoint de verificación de firma recalcula el hash del contenido en la BD y comprueba la firma matemática. Si un byte cambia, la verificación falla matemáticamente. | Cumple ✅ |
