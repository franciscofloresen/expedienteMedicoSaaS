# ============================================================
# MedRecord SaaS — Security Module
# KMS (encryption + signing), WAF, CloudTrail, Secrets Manager
# ============================================================

variable "environment" {
  type = string
}


# ── Data Sources ──
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ============================================================
# KMS — Symmetric CMK for Data Encryption (Envelope Encryption)
# ============================================================
resource "aws_kms_key" "data_encryption" {
  description              = "MedRecord data encryption CMK - ${var.environment}"
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  enable_key_rotation      = true # Annual automatic rotation
  deletion_window_in_days  = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "LambdaEncryptDecrypt"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyWithoutPlaintext",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "lambda.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "medrecord-encryption-cmk-${var.environment}"
    Environment = var.environment
    Purpose     = "data-encryption"
  }
}

resource "aws_kms_alias" "data_encryption" {
  name          = "alias/medrecord-encryption-${var.environment}"
  target_key_id = aws_kms_key.data_encryption.key_id
}

# ============================================================
# KMS — Asymmetric ECDSA Key for Digital Signatures
# Single shared key with EncryptionContext per tenant
# Cost: $1/month (vs $1/key/tenant)
# ============================================================
resource "aws_kms_key" "signing" {
  description              = "MedRecord digital signature key (ECDSA P-256) - ${var.environment}"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = "ECC_NIST_P256"
  deletion_window_in_days  = 30
  # Asymmetric keys do NOT support automatic rotation
  # Migration: create new key → update alias → re-sign critical notes

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "LambdaSignVerify"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = [
          "kms:Sign",
          "kms:Verify",
          "kms:DescribeKey",
          "kms:GetPublicKey"
        ]
        Resource = "*"
        # Signing uses a direct KMS SDK call. kms:ViaService=lambda would never
        # match that request, so scope to the exact execution-role ARN instead.
        Condition = {
          ArnLike = {
            "aws:PrincipalArn" = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/medrecord-lambda-exec-${var.environment}"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "medrecord-signing-ecdsa-${var.environment}"
    Environment = var.environment
    Purpose     = "digital-signatures"
  }
}

resource "aws_kms_alias" "signing" {
  name          = "alias/medrecord-signing-${var.environment}"
  target_key_id = aws_kms_key.signing.key_id
}

# ============================================================
# WAF v2 — 4 Rules (OWASP, SQLi, Bad Inputs, Rate Limit)
# ============================================================
resource "aws_wafv2_web_acl" "api" {
  name        = "medrecord-waf-${var.environment}"
  description = "WAF for MedRecord API - ${var.environment}"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # Rule 1: OWASP Core Rule Set
  rule {
    name     = "aws-managed-common"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }
    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "medrecord-common-rules"
    }
  }

  # Rule 2: SQL Injection Protection
  rule {
    name     = "aws-managed-sqli"
    priority = 2
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesSQLiRuleSet"
      }
    }
    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "medrecord-sqli-rules"
    }
  }

  # Rule 3: Known Bad Inputs (Log4j, etc.)
  rule {
    name     = "aws-managed-bad-inputs"
    priority = 3
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }
    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "medrecord-bad-inputs"
    }
  }

  # Rule 4: Rate Limiting (1000 requests / 5 minutes / IP)
  rule {
    name     = "rate-limit"
    priority = 4
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = 1000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "medrecord-rate-limit"
    }
  }

  visibility_config {
    sampled_requests_enabled   = true
    cloudwatch_metrics_enabled = true
    metric_name                = "medrecord-waf-${var.environment}"
  }

  tags = {
    Name        = "medrecord-waf-${var.environment}"
    Environment = var.environment
  }
}

# ============================================================
# CloudTrail — All management events + S3 data events
# ============================================================
data "aws_iam_policy_document" "cloudtrail_bucket_policy" {
  statement {
    sid    = "AWSCloudTrailAclCheck"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:GetBucketAcl"]
    resources = ["arn:aws:s3:::${var.cloudtrail_bucket_name}"]
  }
  statement {
    sid    = "AWSCloudTrailWrite"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["arn:aws:s3:::${var.cloudtrail_bucket_name}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = var.cloudtrail_bucket_name
  policy = data.aws_iam_policy_document.cloudtrail_bucket_policy.json
}

resource "aws_cloudtrail" "main" {
  depends_on                    = [aws_s3_bucket_policy.cloudtrail]
  name                          = "medrecord-trail-${var.environment}"
  s3_bucket_name                = var.cloudtrail_bucket_name
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true # Tamper detection

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["${var.clinical_bucket_arn}/"]
    }
  }

  tags = {
    Name        = "medrecord-trail-${var.environment}"
    Environment = var.environment
  }
}

variable "cloudtrail_bucket_name" {
  type        = string
  description = "S3 bucket name for CloudTrail logs"
}

variable "clinical_bucket_arn" {
  type        = string
  description = "Clinical S3 bucket ARN included in CloudTrail data events"
}

# ============================================================
# Secrets Manager — DB Credentials with Rotation
# ============================================================
resource "aws_secretsmanager_secret" "app_config" {
  name                    = "medrecord/${var.environment}/app-config-v2"
  description             = "Application configuration secrets"
  kms_key_id              = aws_kms_key.data_encryption.arn
  recovery_window_in_days = var.environment == "prod" ? 30 : 7

  tags = {
    Name        = "medrecord-app-config-${var.environment}"
    Environment = var.environment
  }
}

# ── Outputs ──
output "encryption_key_arn" {
  value = aws_kms_key.data_encryption.arn
}

output "encryption_key_id" {
  value = aws_kms_key.data_encryption.key_id
}

output "signing_key_arn" {
  value = aws_kms_key.signing.arn
}

output "signing_key_id" {
  value = aws_kms_key.signing.key_id
}

output "app_config_secret_arn" {
  value = aws_secretsmanager_secret.app_config.arn
}

output "waf_acl_arn" {
  value = aws_wafv2_web_acl.api.arn
}
