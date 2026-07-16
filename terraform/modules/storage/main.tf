# ============================================================
# MedRecord SaaS — Storage Module
# S3 Buckets: expedientes, audit-logs (WORM), consentimientos
# ============================================================

variable "environment" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "clinical_file_cors_origins" {
  type        = list(string)
  description = "Browser origins allowed to use short-lived clinical file upload forms"

  validation {
    condition     = length(var.clinical_file_cors_origins) > 0
    error_message = "At least one clinical file upload CORS origin is required."
  }
}

# ── Expedientes Bucket (clinical files) ──
resource "aws_s3_bucket" "expedientes" {
  bucket = "medrecord-expedientes-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "medrecord-expedientes-${var.environment}"
    Environment = var.environment
    Purpose     = "clinical-files"
  }
}

resource "aws_s3_bucket_versioning" "expedientes" {
  bucket = aws_s3_bucket.expedientes.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "expedientes" {
  bucket = aws_s3_bucket.expedientes.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "expedientes" {
  bucket = aws_s3_bucket.expedientes.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "expedientes" {
  bucket                  = aws_s3_bucket.expedientes.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "expedientes" {
  bucket = aws_s3_bucket.expedientes.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["POST"]
    allowed_origins = var.clinical_file_cors_origins
    expose_headers  = ["ETag", "x-amz-version-id"]
    max_age_seconds = 300
  }
}

data "aws_iam_policy_document" "expedientes_bucket" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.expedientes.arn, "${aws_s3_bucket.expedientes.arn}/*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyWrongEncryption"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.expedientes.arn}/*"]
    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
    condition {
      test     = "Null"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "expedientes" {
  bucket = aws_s3_bucket.expedientes.id
  policy = data.aws_iam_policy_document.expedientes_bucket.json
}

# NOM-004 Lifecycle: 5-year retention with tiered storage
resource "aws_s3_bucket_lifecycle_configuration" "expedientes" {
  bucket = aws_s3_bucket.expedientes.id

  rule {
    id     = "nom-004-lifecycle"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "STANDARD_IA" # 45% cheaper
    }

    transition {
      days          = 365
      storage_class = "GLACIER_IR" # 83% cheaper
    }

    # No automatic expiry: retention is calculated from the clinical record,
    # not from the individual object's upload date.
  }

  # Deploy-time verification probes are synthetic and must self-clean:
  # the Lambda role deliberately has no s3:DeleteObject.
  rule {
    id     = "expire-healthcheck-probes"
    status = "Enabled"

    filter {
      prefix = "tenants/healthcheck/"
    }

    expiration {
      days = 1
    }

    noncurrent_version_expiration {
      noncurrent_days = 1
    }
  }
}

# ── GuardDuty Malware Protection for newly uploaded clinical files ──
resource "aws_iam_role" "guardduty_malware" {
  name = "medrecord-guardduty-s3-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "malware-protection-plan.guardduty.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "guardduty_malware" {
  name = "clinical-file-scan"
  role = aws_iam_role.guardduty_malware.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ManageEventBridgeRule"
        Effect   = "Allow"
        Action   = ["events:PutRule", "events:DeleteRule", "events:PutTargets", "events:RemoveTargets"]
        Resource = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/DO-NOT-DELETE-AmazonGuardDutyMalwareProtectionS3*"
        Condition = {
          StringLike = {
            "events:ManagedBy" = "malware-protection-plan.guardduty.amazonaws.com"
          }
        }
      },
      {
        Sid      = "InspectEventBridgeRule"
        Effect   = "Allow"
        Action   = ["events:DescribeRule", "events:ListTargetsByRule"]
        Resource = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:rule/DO-NOT-DELETE-AmazonGuardDutyMalwareProtectionS3*"
      },
      {
        Sid      = "TagScannedObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObjectTagging", "s3:GetObjectTagging", "s3:PutObjectVersionTagging", "s3:GetObjectVersionTagging"]
        Resource = "${aws_s3_bucket.expedientes.arn}/tenants/*"
      },
      {
        Sid      = "ConfigureBucketEvents"
        Effect   = "Allow"
        Action   = ["s3:PutBucketNotification", "s3:GetBucketNotification"]
        Resource = aws_s3_bucket.expedientes.arn
      },
      {
        Sid      = "ValidationObject"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.expedientes.arn}/malware-protection-resource-validation-object"
      },
      {
        Sid      = "ValidateBucketOwnership"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.expedientes.arn
      },
      {
        Sid      = "ScanObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "${aws_s3_bucket.expedientes.arn}/tenants/*"
      },
      {
        Sid      = "DecryptObjects"
        Effect   = "Allow"
        Action   = ["kms:GenerateDataKey", "kms:Decrypt"]
        Resource = var.kms_key_arn
        Condition = {
          StringLike = {
            "kms:ViaService" = "s3.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_guardduty_malware_protection_plan" "expedientes" {
  role = aws_iam_role.guardduty_malware.arn

  protected_resource {
    s3_bucket {
      bucket_name     = aws_s3_bucket.expedientes.id
      object_prefixes = ["tenants/"]
    }
  }

  actions {
    tagging {
      status = "ENABLED"
    }
  }

  depends_on = [
    aws_iam_role_policy.guardduty_malware,
    aws_s3_bucket_policy.expedientes,
  ]
}

# ── Audit Logs Bucket (WORM — immutable) ──
resource "aws_s3_bucket" "audit_logs" {
  bucket = "medrecord-audit-${var.environment}-${data.aws_caller_identity.current.account_id}"

  # Object Lock requires versioning (enabled via object_lock_enabled)
  object_lock_enabled = true

  tags = {
    Name        = "medrecord-audit-${var.environment}"
    Environment = var.environment
    Purpose     = "audit-logs-worm"
  }
}

resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket                  = aws_s3_bucket.audit_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Object Lock: COMPLIANCE mode — nobody can delete, not even root
resource "aws_s3_bucket_object_lock_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = 1825 # 5 years — matches NOM-004
    }
  }
}

# ── Consentimientos Bucket (signed PDFs) ──
resource "aws_s3_bucket" "consentimientos" {
  bucket = "medrecord-consent-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "medrecord-consent-${var.environment}"
    Environment = var.environment
    Purpose     = "consent-pdfs"
  }
}

resource "aws_s3_bucket_versioning" "consentimientos" {
  bucket = aws_s3_bucket.consentimientos.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "consentimientos" {
  bucket = aws_s3_bucket.consentimientos.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "consentimientos" {
  bucket                  = aws_s3_bucket.consentimientos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "consentimientos" {
  bucket = aws_s3_bucket.consentimientos.id

  rule {
    id     = "consent-lifecycle"
    status = "Enabled"

    filter {}

    transition {
      days          = 365
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 730
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 1825 # 5 years
    }
  }
}

# ── Frontend Bucket (SPA) ──
resource "aws_s3_bucket" "frontend" {
  bucket = "medrecord-frontend-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "medrecord-frontend-${var.environment}"
    Environment = var.environment
    Purpose     = "spa-hosting"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Lambda Deployment Artifacts ──
# The Lambda ZIP is transient, contains no clinical data and is uploaded by the
# production GitHub Actions role. S3-backed deployment avoids the 50 MiB direct
# upload ceiling while preserving Lambda's 250 MiB uncompressed limit.
resource "aws_s3_bucket" "lambda_artifacts" {
  bucket        = "medrecord-lambda-artifacts-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name        = "medrecord-lambda-artifacts-${var.environment}"
    Environment = var.environment
    Purpose     = "lambda-deployment-artifacts"
  }
}

resource "aws_s3_bucket_ownership_controls" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "lambda_artifacts" {
  bucket                  = aws_s3_bucket.lambda_artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  rule {
    id     = "expire-transient-lambda-artifacts"
    status = "Enabled"

    filter {
      prefix = "lambda/"
    }

    expiration {
      days = 1
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

data "aws_iam_policy_document" "lambda_artifacts" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.lambda_artifacts.arn,
      "${aws_s3_bucket.lambda_artifacts.arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid     = "AllowProductionDeploymentArtifactListing"
    effect  = "Allow"
    actions = ["s3:ListBucket"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/github-actions-deploy-prod"]
    }
    resources = [aws_s3_bucket.lambda_artifacts.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["lambda/*"]
    }
  }

  statement {
    sid    = "AllowProductionDeploymentArtifacts"
    effect = "Allow"
    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/github-actions-deploy-prod"]
    }
    resources = ["${aws_s3_bucket.lambda_artifacts.arn}/lambda/*"]
  }
}

resource "aws_s3_bucket_policy" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  policy = data.aws_iam_policy_document.lambda_artifacts.json
}

# ── Data Sources ──
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Outputs ──
output "expedientes_bucket_name" {
  value = aws_s3_bucket.expedientes.id
}

output "expedientes_bucket_arn" {
  value = aws_s3_bucket.expedientes.arn
}

output "audit_bucket_name" {
  value = aws_s3_bucket.audit_logs.id
}

output "audit_bucket_arn" {
  value = aws_s3_bucket.audit_logs.arn
}

output "consent_bucket_name" {
  value = aws_s3_bucket.consentimientos.id
}

output "consent_bucket_arn" {
  value = aws_s3_bucket.consentimientos.arn
}

output "frontend_bucket_id" {
  value = aws_s3_bucket.frontend.id
}

output "frontend_bucket_regional_domain_name" {
  value = aws_s3_bucket.frontend.bucket_regional_domain_name
}

output "lambda_artifacts_bucket_name" {
  value = aws_s3_bucket.lambda_artifacts.id
}
