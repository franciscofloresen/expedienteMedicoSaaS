# ADR 003: Firma Electrónica ECDSA como Mecanismo No Negociable

## Estado
Aceptado

## Contexto
El sistema cuenta con múltiples capas de trazabilidad y auditoría a nivel de infraestructura: AWS CloudTrail (para la actividad en la nube y llamadas a KMS) y `pgaudit` (para los accesos de lectura/escritura a nivel de PostgreSQL). Debido a que estas herramientas generan un registro robusto de "quién hizo qué", se planteó la opción de eliminar el servicio local de firma criptográfica ECDSA P-256 (implementado en `app/services/firma.py`) para evitar la complejidad de gestionar cargas canónicas, hashes SHA-256 y metadatos de firmas.

## Decisión
Se decidió **rechazar categóricamente la eliminación de la firma ECDSA**. El mecanismo criptográfico asimétrico incrustado en el payload de las notas clínicas debe mantenerse de forma obligatoria.

## Justificación
1. **Requisito Explícito NOM-024 y NOM-004**: La normatividad requiere específicamente la "Firma Electrónica" como el mecanismo vinculante que asegura la integridad del expediente médico.
2. **Naturaleza Legal (No Repudio vs. Trazabilidad)**: Las auditorías en la base de datos (CloudTrail/pgaudit) solo prueban que "un usuario hizo una llamada a la API" o "realizó una inserción SQL". La firma ECDSA crea un vínculo criptográfico exacto entre la *identidad real* (nombre, cédula, especialidad) del médico al momento de firmar y el *contenido canónico exacto* de la nota clínica (diagnósticos, tratamiento, signos vitales).
3. **Inmutabilidad Matemática**: Si un solo caracter de la nota es alterado por cualquier método (incluso una modificación directa a la BD por parte de un administrador con acceso físico/superusuario), la firma matemática se rompe inmediatamente y la manipulación es detectada por la función de verificación. Esto es una protección vital en caso de peritajes legales o auditorías de la Secretaría de Salud.

## Consecuencias
- El sistema incluye un nivel de seguridad de "grado gubernamental" para firmas electrónicas.
- Cualquier actualización de formato en el contenido de las notas clínicas debe conservar siempre la serialización canónica para evitar invalidar las firmas preexistentes.
