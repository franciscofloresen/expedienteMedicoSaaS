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

# ── RDS Instance (Single-AZ for Dev/Pilot) ──
resource "aws_db_instance" "main" {
  identifier        = "medrecord-${var.environment}"
  engine            = "postgres"
  engine_version    = "15.15"
  instance_class    = "db.t4g.micro"
  allocated_storage = 20
  storage_type      = "gp3"

  db_name             = "medrecord"
  username            = var.db_master_username
  # Password managed by Secrets Manager (see security module)
  manage_master_user_password = true

  # Encryption at rest with KMS
  storage_encrypted = true
  kms_key_id        = var.kms_key_arn

  # Backup
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  copy_tags_to_snapshot   = true

  # Protection
  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment == "prod" ? false : true
  final_snapshot_identifier = var.environment == "prod" ? "medrecord-final-${var.environment}" : null

  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]

  # Performance Insights
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = {
    Name        = "medrecord-rds-${var.environment}"
    Environment = var.environment
    Project     = "medrecord"
  }
}



# ── Outputs ──
output "cluster_endpoint" {
  value = aws_db_instance.main.endpoint
}


output "cluster_arn" {
  value = aws_db_instance.main.arn
}

output "db_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}
