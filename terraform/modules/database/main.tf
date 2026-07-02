# ============================================================
# MedRecord SaaS — Database Module
# Amazon RDS PostgreSQL (db.t4g.small)
# ============================================================

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "rds_security_group_id" {
  type = string
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS CMK for encryption at rest"
}

variable "db_master_username" {
  type    = string
  default = "medrecord_admin"
}

# ── DB Subnet Group ──
resource "aws_db_subnet_group" "main" {
  name       = "medrecord-${var.environment}"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "medrecord-db-subnet-${var.environment}"
    Environment = var.environment
  }
}

# ── Parameter Group for pgAudit (RDS Instance) ──
resource "aws_db_parameter_group" "postgresql_audit" {
  name   = "medrecord-rds-audit-pg15-${var.environment}"
  family = "postgres15"

  parameter {
    name         = "shared_preload_libraries"
    value        = "pgaudit"
    apply_method = "pending-reboot"
  }

  parameter {
    name         = "pgaudit.log"
    value        = "read, write"
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

  tags = {
    Environment = var.environment
  }
}

# ── RDS PostgreSQL Instance ──
resource "aws_db_instance" "main" {
  identifier                  = "medrecord-${var.environment}"
  engine                      = "postgres"
  engine_version              = "15.17"
  instance_class              = "db.t4g.small"
  
  allocated_storage           = 20
  max_allocated_storage       = 100
  storage_type                = "gp3"

  db_name                     = "medrecord"
  username                    = var.db_master_username
  manage_master_user_password = true

  storage_encrypted           = true
  kms_key_id                  = var.kms_key_arn

  db_subnet_group_name        = aws_db_subnet_group.main.name
  vpc_security_group_ids      = [var.rds_security_group_id]

  parameter_group_name        = aws_db_parameter_group.postgresql_audit.name

  backup_retention_period     = 35
  backup_window               = "03:00-04:00"
  copy_tags_to_snapshot       = true

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  deletion_protection         = var.environment == "prod" ? true : false
  skip_final_snapshot         = var.environment == "prod" ? false : true
  final_snapshot_identifier   = var.environment == "prod" ? "medrecord-final-${var.environment}" : null

  tags = {
    Name        = "medrecord-rds-${var.environment}"
    Environment = var.environment
    Project     = "medrecord"
  }
}

# ── Outputs ──
# Keeping output names identical so other modules don't break
output "cluster_endpoint" {
  value = aws_db_instance.main.address
}

output "cluster_arn" {
  value = aws_db_instance.main.arn
}

output "db_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}