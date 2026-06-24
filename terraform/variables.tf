variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "alarm_email" {
  type        = string
  description = "Email for alarm notifications"
}

variable "clerk_secret_key" {
  description = "Clerk API Secret Key"
  type        = string
  sensitive   = true
}

variable "clerk_issuer_url" {
  description = "Clerk Issuer URL"
  type        = string
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL"
  type        = string
}
