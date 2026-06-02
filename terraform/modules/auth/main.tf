# ============================================================
# MedRecord SaaS — Auth Module
# Cognito User Pool with MFA, strong password policy
# ============================================================

variable "environment" {
  type = string
}

# ── Cognito User Pool ──
resource "aws_cognito_user_pool" "main" {
  name = "medrecord-${var.environment}"

  # Username = email
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # MFA — mandatory (NOM-024 access control requirement)
  mfa_configuration = "ON"

  software_token_mfa_configuration {
    enabled = true
  }

  # Strong password policy
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User attribute schema
  schema {
    name                     = "tenant_id"
    attribute_data_type      = "String"
    mutable                  = false
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 36
      max_length = 36
    }
  }

  schema {
    name                = "cedula"
    attribute_data_type = "String"
    mutable             = true

    string_attribute_constraints {
      min_length = 5
      max_length = 20
    }
  }

  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # Prevent user enumeration attacks
  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = {
    Name        = "medrecord-pool-${var.environment}"
    Environment = var.environment
  }
}

# ── App Client ──
resource "aws_cognito_user_pool_client" "app" {
  name                                 = "medrecord-app-${var.environment}"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = false # SPA doesn't use client secret
  prevent_user_existence_errors        = "ENABLED"
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  # Token lifetimes
  access_token_validity  = 15   # 15 minutes
  id_token_validity      = 15   # 15 minutes
  refresh_token_validity = 7    # 7 days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  # Callback URLs (update with actual domain)
  callback_urls = var.environment == "prod" ? [
    "https://app.medrecord.mx/callback"
  ] : [
    "http://localhost:5173/callback",
    "https://${var.environment}.medrecord.mx/callback"
  ]

  logout_urls = var.environment == "prod" ? [
    "https://app.medrecord.mx"
  ] : [
    "http://localhost:5173",
    "https://${var.environment}.medrecord.mx"
  ]
}

# ── Outputs ──
output "user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.main.arn
}

output "client_id" {
  value = aws_cognito_user_pool_client.app.id
}
