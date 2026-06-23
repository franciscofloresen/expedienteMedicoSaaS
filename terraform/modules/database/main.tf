# ============================================================
# MedRecord SaaS — Database Module
# Aurora Serverless v2 (PostgreSQL 15.4) + RDS Proxy
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

# ── Parameter Group for pgAudit (Aurora Cluster) ──
resource "aws_rds_cluster_parameter_group" "postgresql_audit" {
  name   = "medrecord-aurora-audit-pg15-${var.environment}"
  family = "aurora-postgresql15"

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

# ── Aurora Serverless v2 Cluster ──
resource "aws_rds_cluster" "main" {
  cluster_identifier        = "medrecord-${var.environment}"
  engine                    = "aurora-postgresql"
  engine_mode               = "provisioned"
  engine_version            = "15.12"
  database_name             = "medrecord"
  master_username           = var.db_master_username
  manage_master_user_password = true
  
  storage_encrypted = true
  kms_key_id        = var.kms_key_arn

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]

  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.postgresql_audit.name

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2.0
  }

  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"
  copy_tags_to_snapshot   = true

  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment == "prod" ? false : true
  final_snapshot_identifier = var.environment == "prod" ? "medrecord-final-${var.environment}" : null

  tags = {
    Name        = "medrecord-aurora-${var.environment}"
    Environment = var.environment
    Project     = "medrecord"
  }
}

# ── Aurora Serverless v2 Instance ──
resource "aws_rds_cluster_instance" "main" {
  cluster_identifier = aws_rds_cluster.main.id
  identifier         = "medrecord-instance-${var.environment}"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
  instance_class     = "db.serverless"
  
  db_subnet_group_name = aws_db_subnet_group.main.name

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = {
    Name        = "medrecord-aurora-instance-${var.environment}"
    Environment = var.environment
  }
}

# ── Outputs ──
output "cluster_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "cluster_arn" {
  value = aws_rds_cluster.main.arn
}

output "db_secret_arn" {
  value = aws_rds_cluster.main.master_user_secret[0].secret_arn
}
