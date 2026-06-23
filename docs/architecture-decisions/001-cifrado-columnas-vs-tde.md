# ADR 001: Mantenimiento de Cifrado a Nivel de Columna junto a TDE

## Estado
Aceptado

## Contexto
El backend de Expediente Médico opera sobre Amazon Aurora Serverless v2, el cual cuenta con Transparent Data Encryption (TDE) activado por defecto. TDE garantiza que los datos en reposo a nivel de almacenamiento (volúmenes EBS) y los snapshots estén cifrados. Surgió la pregunta de si esto nos permitía eliminar la lógica de cifrado a nivel de columna gestionada por la aplicación (Application-Level Encryption) para simplificar la arquitectura.

La normativa mexicana aplicable a los Expedientes Clínicos Electrónicos (NOM-004-SSA3-2012 y NOM-024-SSA3-2012) exige controles estrictos de confidencialidad, integridad y trazabilidad para proteger la Información Personal de Salud (PHI).

## Decisión
Se decidió **mantener el cifrado a nivel de columna (vía AWS KMS)** para los datos más sensibles, como `domicilio_cifrado` y `antecedentes_cifrado`, actuando en conjunto con TDE. 

## Justificación
1. **Defensa en Profundidad**: TDE protege contra el robo físico de discos o fugas de snapshots de bajo nivel, pero resulta transparente para la base de datos. Si un atacante compromete la base de datos (ej. SQL Injection) o si un administrador de BD obtiene acceso irrestricto, TDE devolverá los datos en texto plano. 
2. **Segregación de Privilegios**: Al usar cifrado a nivel de columna con KMS, el motor de base de datos nunca ve los datos confidenciales en texto plano. Se requiere que el atacante comprometa tanto la base de datos como los permisos de IAM para llamar a `kms:Decrypt`, limitando severamente la superficie de exposición.
3. **Cumplimiento y Auditoría**: AWS CloudTrail audita cada llamada a KMS, permitiéndonos demostrar ante cualquier regulador exactamente cuándo y quién (qué rol o tenant) descifró una columna específica.

## Consecuencias
- Mayor complejidad en la capa de servicios (cifrado/descifrado en Python).
- Imposibilidad de hacer consultas SQL complejas (ej. `LIKE` o `ORDER BY`) sobre las columnas cifradas.
- Mayor seguridad y alineación innegable con las NOM de la Secretaría de Salud.
