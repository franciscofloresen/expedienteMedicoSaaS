# Runbook: Migración de RDS a Aurora Serverless v2

Este documento describe el proceso para migrar la base de datos PostgreSQL estándar (instancia RDS) a un clúster de **Aurora Serverless v2**, manteniendo habilitado el sistema de auditoría `pgaudit`.

> [!WARNING]
> **Riesgo de Pérdida de Datos**
> Modificar el bloque de infraestructura de `aws_db_instance` a `aws_rds_cluster` en Terraform es una operación destructiva. Terraform eliminará la instancia actual de RDS y creará un nuevo clúster de Aurora vacío si no se siguen los pasos de este runbook.

## Prerrequisitos
- Acceso a la consola de AWS o AWS CLI con permisos de administrador sobre RDS.
- Haber notificado a los usuarios sobre la ventana de mantenimiento (el sistema estará inactivo durante la migración).

## Pasos para la Migración (Fase 2)

### 1. Ventana de Mantenimiento y Snapshot Manual
1. Detén el tráfico de la aplicación hacia la base de datos (por ejemplo, bajando las lambdas o activando una página de mantenimiento en CloudFront/WAF).
2. Crea un **Snapshot Manual** de la instancia RDS actual (`medrecord-prod`).
3. Anota el identificador del snapshot (ej. `medrecord-prod-pre-aurora-migration`).

### 2. Modificación del Código Terraform
Edita el archivo `terraform/modules/database/main.tf`:

1. **Parameter Group**: Cambia el `aws_db_parameter_group` actual por un `aws_rds_cluster_parameter_group` y ajusta `family = "aurora-postgresql15"`.
2. **Reemplazo de Instancia**:
   - Borra el recurso `aws_db_instance.main`.
   - Crea el recurso `aws_rds_cluster.main` (el clúster) apuntando a la configuración serverless.
   - **IMPORTANTE**: Asegúrate de agregar el atributo `snapshot_identifier = "medrecord-prod-pre-aurora-migration"` en el bloque del clúster para que se inicie con los datos de tu snapshot manual.
   - Crea el recurso `aws_rds_cluster_instance.main` para la instancia de escritura.
3. **Outputs**: Actualiza `cluster_endpoint` para que referencie `aws_rds_cluster.main.endpoint`.

### 3. Ejecución de Terraform
1. Ejecuta `terraform plan` y verifica detalladamente que el clúster nuevo usará el `snapshot_identifier`.
2. Ejecuta `terraform apply`. Terraform destruirá la instancia vieja y levantará el nuevo clúster de Aurora restaurado a partir de los datos.

### 4. Verificación
1. Conéctate a la nueva base de datos para confirmar que los datos existen y que el usuario `medrecord_app` tiene acceso.
2. Levanta de nuevo los servicios de aplicación.
3. Ejecuta una operación de prueba en la app y confirma en CloudWatch / logs de Postgres que `pgaudit` está escribiendo correctamente las sentencias.

Una vez finalizado y comprobado, puedes remover el `snapshot_identifier` de tu código Terraform en un commit posterior si lo deseas, para evitar dependencias hardcodeadas, utilizando comandos de `lifecycle { ignore_changes = [snapshot_identifier] }`.
