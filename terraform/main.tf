# ============================================================
# MedRecord SaaS — Root Infrastructure
# ============================================================

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "medrecord-terraform-state"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "medrecord-terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "medrecord"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ── Networking ──
module "networking" {
  source      = "./modules/networking"
  environment = var.environment
}

# ── Security (KMS, WAF, CloudTrail, Secrets) ──
module "security" {
  source                = "./modules/security"
  environment           = var.environment
  cloudtrail_bucket_name = module.storage.audit_bucket_name
}

# ── Storage (S3 buckets) ──
module "storage" {
  source      = "./modules/storage"
  environment = var.environment
  kms_key_arn = module.security.encryption_key_arn
}

# ── Database (Aurora Serverless v2) ──
module "database" {
  source                   = "./modules/database"
  environment              = var.environment
  vpc_id                   = module.networking.vpc_id
  private_subnet_ids       = module.networking.private_subnet_ids
  rds_security_group_id    = module.networking.rds_security_group_id
  kms_key_arn              = module.security.encryption_key_arn
}

# ── Compute (Lambda + API Gateway) ──
module "compute" {
  source                   = "./modules/compute"
  environment              = var.environment
  vpc_id                   = module.networking.vpc_id
  private_subnet_ids       = module.networking.private_subnet_ids
  lambda_security_group_id = module.networking.lambda_security_group_id
  db_secret_arn            = module.database.db_secret_arn
  db_cluster_endpoint      = module.database.cluster_endpoint
  encryption_key_arn       = module.security.encryption_key_arn
  signing_key_arn          = module.security.signing_key_arn
  s3_expedientes_bucket    = module.storage.expedientes_bucket_name
  s3_audit_bucket          = module.storage.audit_bucket_name
  s3_consent_bucket        = module.storage.consent_bucket_name
  waf_acl_arn              = module.security.waf_acl_arn
  frontend_url             = "https://${module.cdn.cloudfront_domain_name}"
}

# ── Observability (Alarms, SNS) ──
module "observability" {
  source               = "./modules/observability"
  environment          = var.environment
  alarm_email          = var.alarm_email
  db_cluster_id        = "medrecord-${var.environment}"
  health_check_fqdn    = ""  # No custom domain in dev
  lambda_function_name = "medrecord-api-${var.environment}"
  api_name             = "medrecord-api-${var.environment}"
  depends_on           = [module.compute]
}

# ── CDN (CloudFront) ──
module "cdn" {
  source                         = "./modules/cdn"
  environment                    = var.environment
  s3_bucket_regional_domain_name = module.storage.frontend_bucket_regional_domain_name
  s3_bucket_id                   = module.storage.frontend_bucket_id
}

# ── Outputs ──
output "vpc_id" {
  value = module.networking.vpc_id
}

output "db_cluster_endpoint" {
  value = module.database.cluster_endpoint
}

output "encryption_key_arn" {
  value = module.security.encryption_key_arn
}

output "signing_key_arn" {
  value = module.security.signing_key_arn
}
