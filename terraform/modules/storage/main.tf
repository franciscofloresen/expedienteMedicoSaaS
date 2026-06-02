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

    expiration {
      days = 1825 # 5 years = NOM-004 minimum
    }
  }
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

# ── Data Sources ──
data "aws_caller_identity" "current" {}

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
