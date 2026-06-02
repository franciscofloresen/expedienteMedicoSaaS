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

variable "lambda_security_group_id" {
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

# ── Aurora Cluster ──
resource "aws_rds_cluster" "main" {
  cluster_identifier = "medrecord-${var.environment}"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = "15.4"

  database_name   = "medrecord"
  master_username = var.db_master_username
  # Password managed by Secrets Manager (see security module)
  manage_master_user_password = true

  # Encryption at rest with KMS
  storage_encrypted = true
  kms_key_id        = var.kms_key_arn

  # Backup — RPO < 5 minutes (Aurora PITR is automatic)
  backup_retention_period = 35 # Maximum retention, free with Aurora
  preferred_backup_window = "03:00-04:00"
  copy_tags_to_snapshot   = true

  # Protection
  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment == "prod" ? false : true
  final_snapshot_identifier = var.environment == "prod" ? "medrecord-final-${var.environment}" : null

  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_security_group_id]

  # Performance Insights (free for 7-day retention)
  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  # Serverless v2 scaling config
  serverlessv2_scaling_configuration {
    min_capacity = 0.5 # $43/month — sufficient for MVP
    max_capacity = 4.0 # Auto-scales under load
  }

  # CloudWatch log exports
  enabled_cloudwatch_logs_exports = ["postgresql"]

  tags = {
    Name        = "medrecord-aurora-${var.environment}"
    Environment = var.environment
    Project     = "medrecord"
  }
}

# ── Aurora Writer Instance (Serverless v2) ──
resource "aws_rds_cluster_instance" "writer" {
  identifier         = "medrecord-${var.environment}-w1"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  performance_insights_enabled          = true
  performance_insights_retention_period = 7

  tags = {
    Name        = "medrecord-writer-${var.environment}"
    Environment = var.environment
    Role        = "writer"
  }
}

# ── RDS Proxy (Connection Pooling for Lambda) ──
resource "aws_db_proxy" "main" {
  name                   = "medrecord-proxy-${var.environment}"
  debug_logging          = var.environment != "prod"
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 300 # 5 minutes
  require_tls            = true
  role_arn               = aws_iam_role.rds_proxy.arn
  vpc_security_group_ids = [var.lambda_security_group_id]
  vpc_subnet_ids         = var.private_subnet_ids

  auth {
    auth_scheme = "SECRETS"
    description = "Authenticate via Secrets Manager"
    iam_auth    = "REQUIRED"
    secret_arn  = aws_rds_cluster.main.master_user_secret[0].secret_arn
  }

  tags = {
    Name        = "medrecord-proxy-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_db_proxy_default_target_group" "main" {
  db_proxy_name = aws_db_proxy.main.name

  connection_pool_config {
    max_connections_percent      = 90
    max_idle_connections_percent = 50
    connection_borrow_timeout    = 120
  }
}

resource "aws_db_proxy_target" "main" {
  db_proxy_name         = aws_db_proxy.main.name
  target_group_name     = aws_db_proxy_default_target_group.main.name
  db_cluster_identifier = aws_rds_cluster.main.id
}

# ── IAM Role for RDS Proxy ──
resource "aws_iam_role" "rds_proxy" {
  name = "medrecord-rds-proxy-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "rds.amazonaws.com"
      }
    }]
  })

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_role_policy" "rds_proxy_secrets" {
  name = "secrets-access"
  role = aws_iam_role.rds_proxy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [aws_rds_cluster.main.master_user_secret[0].secret_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [var.kms_key_arn]
      }
    ]
  })
}

# ── Outputs ──
output "cluster_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "cluster_reader_endpoint" {
  value = aws_rds_cluster.main.reader_endpoint
}

output "proxy_endpoint" {
  value = aws_db_proxy.main.endpoint
}

output "cluster_arn" {
  value = aws_rds_cluster.main.arn
}

output "db_secret_arn" {
  value = aws_rds_cluster.main.master_user_secret[0].secret_arn
}
