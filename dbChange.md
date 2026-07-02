# Migración: Aurora Serverless v2 → RDS PostgreSQL db.t4g.small

## Contexto
Estamos en beta con poco tráfico. Aurora Serverless v2 cuesta ~$43/mes
mínimo incluso sin uso. Migramos a RDS PostgreSQL estándar db.t4g.small
(~$25/mes) sin cambiar nada en el backend — mismo engine, mismo PostgreSQL 15.

## IMPORTANTE antes de empezar
1. Tomar un snapshot manual de Aurora AHORA antes de cualquier cambio:
   aws rds create-db-cluster-snapshot \
     --db-cluster-identifier <tu-cluster-id> \
     --db-cluster-snapshot-identifier cloudmedrecord-pre-migration-$(date +%Y%m%d)

2. Este cambio DESTRUYE la base de datos Aurora y crea una nueva instancia RDS.
   Requiere una ventana de mantenimiento con downtime planificado.
   Tiempo estimado: 20-30 minutos.

3. Leer docs/runbooks/aurora_migration.md antes de aplicar.

## Cambios en Terraform (terraform/modules/database/main.tf)

### ELIMINAR estos recursos:
- aws_rds_cluster.main
- aws_rds_cluster_instance.main
- aws_rds_cluster_parameter_group.postgresql_audit (si existe)

### CREAR estos recursos:

resource "aws_db_parameter_group" "postgresql_audit" {
  name   = "cloudmedrecord-audit-pg15-${var.environment}"
  family = "postgres15"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pgaudit"
    apply_method = "pending-reboot"
  }
  parameter {
    name         = "pgaudit.log"
    value        = "read,write"
    apply_method = "immediate"
  }
  parameter {
    name         = "pgaudit.log_catalog"
    value        = "off"
    apply_method = "immediate"
  }
  parameter {
    name         = "pgaudit.role"
    value        = "rds_pgaudit"
    apply_method = "immediate"
  }
}

resource "aws_db_instance" "main" {
  identifier        = "cloudmedrecord-${var.environment}"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t4g.small"

  db_name  = "medrecord"
  username = var.db_username
  password = var.db_password

  allocated_storage     = 20
  storage_type          = "gp3"
  storage_encrypted     = true

  parameter_group_name = aws_db_parameter_group.postgresql_audit.name

  backup_retention_period = 35
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "cloudmedrecord-${var.environment}-final"

  # NO multi-AZ para beta — lo activamos cuando tengamos clientes de pago
  multi_az = false

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  # TODO: Migrar a Multi-AZ cuando lleguen los primeros 10 clientes de pago
}

### ACTUALIZAR outputs:
# Cambiar de cluster_endpoint a aws_db_instance.main.endpoint
# Cambiar de aws_rds_cluster.main.master_user_secret a
#   aws_db_instance.main.master_user_secret (si usas Secrets Manager)
#   o usar la variable db_password directamente

## Proceso de migración de datos

Después del terraform apply:

1. Restaurar datos desde el snapshot de Aurora:
   - Crear instancia temporal desde el snapshot
   - pg_dump desde la instancia temporal
   - pg_restore hacia la nueva instancia RDS

2. Verificar que pgaudit está activo:
   SHOW pgaudit.log;
   -- Debe devolver: read,write

3. Recrear el rol rds_pgaudit:
   CREATE ROLE rds_pgaudit;
   GRANT rds_pgaudit TO medrecord_app;

4. Re-ejecutar las migraciones de Alembic:
   alembic upgrade head

5. Verificar RLS y triggers de inmutabilidad:
   -- Confirmar que los triggers existen en notas y expedientes
   SELECT trigger_name, event_object_table
   FROM information_schema.triggers
   WHERE trigger_schema = 'public';

## Variables que necesitan actualizarse
- Cualquier referencia a "aurora" en variables de entorno o Secrets Manager
- El DATABASE_URL en backend/.env y en Lambda environment variables:
  postgresql+asyncpg://user:pass@<nuevo-endpoint>/medrecord

## NO tocar
- Lógica de RLS en session.py
- pgaudit ya está configurado en el nuevo parameter group
- encrypt_field() / decrypt_field() — siguen funcionando igual
- firma.py — sin cambios
- Toda la lógica de aplicación es agnóstica al engine de AWS

## Verificación final
Después de migrar, correr:
  PYTHONPATH=. python scripts/smoke_test.py
Para confirmar que el flujo completo (onboarding → nota → firma → verificación)
funciona contra la nueva instancia.