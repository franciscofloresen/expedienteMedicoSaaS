# ADR 002: Conservación de la Tabla tenant_key.py como Placeholder

## Estado
Aceptado

## Contexto
En la arquitectura inicial, se planteó un sistema de "Envelope Encryption" donde el backend generaba una llave única de datos (DEK) por tenant, la cual se cifraba con KMS y se almacenaba en la tabla `tenant_key`. Recientemente, para reducir la complejidad operativa y apoyarnos más en los servicios manejados, simplificamos el cifrado delegándolo de forma directa a la llave CMK de AWS KMS, haciendo innecesaria la generación de DEKs locales.

## Decisión
Se decidió **no eliminar el modelo de base de datos `tenant_key.py` ni la tabla subyacente**. En lugar de almacenar un DEK real, el flujo de Onboarding ahora guarda un placeholder inactivo en `encrypted_dek` (`b"unused_direct_kms"`) y almacena el ARN del KMS activo en `kms_key_id`.

## Justificación
1. **Auditoría de Rotación de Llaves**: A medida que el SaaS crezca, la llave maestra (CMK) en AWS KMS será rotada de forma automática o manual. La tabla `tenant_key` servirá como un registro inmutable que audita exactamente bajo qué versión de la llave o qué ARN específico se inicializó la seguridad de cada consultorio.
2. **Mitigación de Riesgos Estructurales**: Realizar migraciones destructivas (eliminar tablas o columnas) en una base de datos clínica que será auditada conlleva riesgos operativos. Mantener el modelo inactivo como placeholder tiene un impacto de costo o rendimiento de $0, pero reserva el espacio en caso de que futuras expansiones requieran reactivar el flujo de Envelope Encryption (por ejemplo, si los costos de peticiones a KMS directas escalan demasiado).

## Consecuencias
- La base de datos tiene una tabla cuyo propósito de diseño original evolucionó hacia un registro de metadatos criptográficos de solo-lectura.
- El código se mantiene a salvo de refactorizaciones destructivas innecesarias.
